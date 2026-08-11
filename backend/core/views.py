from __future__ import annotations

from django.db.models import Count, Q
import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Application,
    ApplicationEvent,
    Artifact,
    JobMatch,
    JobPosting,
    JobSource,
    ProfileDocument,
    ProfileFact,
    Resume,
)
from .realtime_events import publish_user_event
from .serializers import (
    ApplicationEventSerializer,
    ApplicationSerializer,
    ArtifactSerializer,
    JobImportSerializer,
    JobMatchSerializer,
    JobPostingSerializer,
    JobSourceSerializer,
    ProfileDocumentSerializer,
    ProfileFactSerializer,
    ResumeSerializer,
    ResumeTailorSerializer,
)
from .services import create_tailored_resume, dashboard, generate_strategy, import_job_posting, ingest_profile_document, recompute_match
from .tasks import ingest_profile_document_task, recompute_all_matches_task, recompute_job_match_task


def enqueue_profile_ingestion(document: ProfileDocument) -> dict:
    try:
        task = ingest_profile_document_task.delay(document.id)
        return {'mode': 'async', 'task_id': task.id}
    except Exception:
        publish_user_event(document.owner_id, 'profile_ingestion_started', {'document_id': document.id})
        result = ingest_profile_document(document)
        publish_user_event(document.owner_id, 'profile_ingestion_finished', {'document_id': document.id, **result})
        return {'mode': 'sync', **result}


class OwnedViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class ProfileDocumentViewSet(OwnedViewSet):
    serializer_class = ProfileDocumentSerializer
    queryset = ProfileDocument.objects.all()

    def perform_create(self, serializer):
        document = serializer.save(owner=self.request.user)
        document.status = 'queued'
        document.status_message = 'Queued for ingestion'
        document.save(update_fields=['status', 'status_message', 'updated_at'])
        enqueue_profile_ingestion(document)

    @action(detail=True, methods=['post'])
    def ingest(self, request, pk=None):
        document = self.get_object()
        document.status = 'queued'
        document.status_message = 'Queued for ingestion'
        document.save(update_fields=['status', 'status_message', 'updated_at'])
        result = enqueue_profile_ingestion(document)
        return Response({'status': document.status, **result})


class ProfileFactViewSet(OwnedViewSet):
    serializer_class = ProfileFactSerializer
    queryset = ProfileFact.objects.select_related('source_document', 'source_chunk').all()

    def get_queryset(self):
        qs = super().get_queryset()
        fact_type = self.request.query_params.get('fact_type')
        verified = self.request.query_params.get('verified')
        search = self.request.query_params.get('search')
        if fact_type:
            qs = qs.filter(fact_type=fact_type)
        if verified in {'true', 'false'}:
            qs = qs.filter(verified_by_user=(verified == 'true'))
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(statement__icontains=search))
        return qs

    def perform_update(self, serializer):
        fact = serializer.save()
        from .ai import embed_text

        fact.embedding = embed_text(f'{fact.title}\n{fact.statement}')
        fact.save(update_fields=['embedding', 'updated_at'])
        publish_user_event(self.request.user.id, 'profile_fact_updated', {'fact_id': fact.id})

    def perform_destroy(self, instance):
        fact_id = instance.id
        instance.delete()
        publish_user_event(self.request.user.id, 'profile_fact_deleted', {'fact_id': fact_id})

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        fact = self.get_object()
        fact.verified_by_user = True
        fact.save(update_fields=['verified_by_user', 'updated_at'])
        publish_user_event(request.user.id, 'profile_fact_updated', {'fact_id': fact.id})
        return Response(self.get_serializer(fact).data)


class JobSourceViewSet(OwnedViewSet):
    serializer_class = JobSourceSerializer
    queryset = JobSource.objects.all()

    def get_queryset(self):
        return super().get_queryset().annotate(job_count=Count('jobs'))

    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        source = self.get_object()
        source.last_run_at = timezone.now()
        source.last_status = 'queued'
        source.last_message = 'Source connector hooks are ready; manual import is implemented in MVP.'
        source.save(update_fields=['last_run_at', 'last_status', 'last_message', 'updated_at'])
        publish_user_event(request.user.id, 'source_run_finished', {'source_id': source.id, 'created_jobs': 0})
        return Response(self.get_serializer(source).data)


class JobPostingViewSet(OwnedViewSet):
    serializer_class = JobPostingSerializer
    queryset = JobPosting.objects.select_related('source', 'match').all()

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get('search')
        status_value = self.request.query_params.get('status')
        remote_policy = self.request.query_params.get('remote_policy')
        min_score = self.request.query_params.get('min_score')
        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(company__icontains=search)
                | Q(description_text__icontains=search)
            )
        if status_value:
            qs = qs.filter(status=status_value)
        if remote_policy:
            qs = qs.filter(remote_policy=remote_policy)
        if min_score:
            try:
                qs = qs.filter(match__score__gte=int(min_score))
            except ValueError:
                pass
        return qs

    @action(detail=False, methods=['post'])
    def import_job(self, request):
        serializer = JobImportSerializer(data=request.data, owner=request.user)
        serializer.is_valid(raise_exception=True)
        job = import_job_posting(
            request.user,
            text=serializer.validated_data['text'],
            source_url=serializer.validated_data.get('source_url', ''),
            source=serializer.validated_data.get('source'),
        )
        publish_user_event(request.user.id, 'job_imported', {'job_id': job.id})
        return Response(self.get_serializer(job).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def recompute_match(self, request, pk=None):
        job = self.get_object()
        task = recompute_job_match_task.delay(job.id)
        return Response({'task_id': task.id})

    @action(detail=True, methods=['post'])
    def create_application(self, request, pk=None):
        job = self.get_object()
        application, _ = Application.objects.get_or_create(
            owner=request.user,
            job=job,
            defaults={'status': 'saved', 'notes': ''},
        )
        return Response(ApplicationSerializer(application, context={'request': request}).data, status=status.HTTP_201_CREATED)


class JobMatchViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = JobMatchSerializer
    queryset = JobMatch.objects.select_related('job').all()

    def get_queryset(self):
        qs = self.queryset.filter(owner=self.request.user)
        min_score = self.request.query_params.get('min_score')
        if min_score:
            try:
                qs = qs.filter(score__gte=int(min_score))
            except ValueError:
                pass
        return qs

    @action(detail=False, methods=['post'])
    def recompute(self, request):
        task = recompute_all_matches_task.delay(request.user.id)
        return Response({'task_id': task.id})


class ResumeViewSet(OwnedViewSet):
    serializer_class = ResumeSerializer
    queryset = Resume.objects.select_related('target_job', 'parent_resume').prefetch_related('claims').all()

    def get_queryset(self):
        qs = super().get_queryset()
        kind = self.request.query_params.get('kind')
        job_id = self.request.query_params.get('job')
        if kind:
            qs = qs.filter(kind=kind)
        if job_id:
            qs = qs.filter(target_job_id=job_id)
        return qs

    @action(detail=False, methods=['post'])
    def tailor(self, request):
        serializer = ResumeTailorSerializer(data=request.data, owner=request.user)
        serializer.is_valid(raise_exception=True)
        resume = create_tailored_resume(
            request.user,
            job=serializer.validated_data['job'],
            canonical=serializer.validated_data.get('canonical_resume'),
        )
        publish_user_event(request.user.id, 'resume_tailoring_finished', {'resume_id': resume.id, 'job_id': resume.target_job_id})
        return Response(self.get_serializer(resume).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        resume = self.get_object()
        resume.approved = True
        resume.save(update_fields=['approved', 'updated_at'])
        return Response(self.get_serializer(resume).data)

    @action(detail=True, methods=['get'])
    def export_markdown(self, request, pk=None):
        resume = self.get_object()
        response = HttpResponse(resume.content_markdown, content_type='text/markdown')
        filename = f'{resume.title.lower().replace(" ", "-")}.md'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class ApplicationViewSet(OwnedViewSet):
    serializer_class = ApplicationSerializer
    queryset = Application.objects.select_related('job', 'resume').prefetch_related('events', 'artifacts').all()

    def get_queryset(self):
        qs = super().get_queryset()
        status_value = self.request.query_params.get('status')
        search = self.request.query_params.get('search')
        if status_value:
            qs = qs.filter(status=status_value)
        if search:
            qs = qs.filter(Q(job__title__icontains=search) | Q(job__company__icontains=search) | Q(notes__icontains=search))
        return qs

    def perform_create(self, serializer):
        application = serializer.save(owner=self.request.user)
        ApplicationEvent.objects.create(
            owner=self.request.user,
            application=application,
            event_type='created',
            happened_at=timezone.now(),
            notes=f'Application created with status {application.status}.',
        )

    def perform_update(self, serializer):
        old_status = self.get_object().status
        application = serializer.save()
        if application.status != old_status:
            ApplicationEvent.objects.create(
                owner=self.request.user,
                application=application,
                event_type='status_changed',
                happened_at=timezone.now(),
                notes=f'Status changed from {old_status} to {application.status}.',
            )
            publish_user_event(self.request.user.id, 'application_updated', {'application_id': application.id, 'status': application.status})


class ApplicationEventViewSet(OwnedViewSet):
    serializer_class = ApplicationEventSerializer
    queryset = ApplicationEvent.objects.select_related('application').all()

    def get_queryset(self):
        qs = super().get_queryset()
        application = self.request.query_params.get('application')
        if application:
            qs = qs.filter(application_id=application)
        return qs


class ArtifactViewSet(OwnedViewSet):
    serializer_class = ArtifactSerializer
    queryset = Artifact.objects.select_related('application', 'resume').all()


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(dashboard(request.user))


class StrategyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(generate_strategy(request.user))


class FrontendAppView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, path: str = ''):
        static_root = Path(settings.BASE_DIR) / 'staticfiles'
        requested = (static_root / path).resolve() if path else static_root / 'index.html'
        if static_root.resolve() in requested.parents and requested.exists() and requested.is_file():
            content_type, _ = mimetypes.guess_type(str(requested))
            return FileResponse(open(requested, 'rb'), content_type=content_type or 'application/octet-stream')
        index = static_root / 'index.html'
        if index.exists():
            return FileResponse(open(index, 'rb'), content_type='text/html')
        raise Http404('Frontend build not found.')
