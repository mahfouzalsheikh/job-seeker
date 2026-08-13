from __future__ import annotations

import mimetypes
from pathlib import Path

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    AgentRun,
    Application,
    ApplicationEvent,
    ApprovalRequest,
    Artifact,
    CandidatePreference,
    ConversationThread,
    CoverLetter,
    JobMatch,
    JobPosting,
    JobSource,
    ProfileDocument,
    ProfileFact,
    Resume,
    SourceRun,
)
from .realtime_events import publish_user_event
from .domain.documents import render_pdf, validate_resume_claims
from .serializers import (
    AgentRunSerializer,
    ApplicationEventSerializer,
    ApplicationSerializer,
    ApprovalRequestSerializer,
    ArtifactSerializer,
    CandidatePreferenceSerializer,
    CandidateProfileSerializer,
    ConversationThreadSerializer,
    CoverLetterSerializer,
    JobImportSerializer,
    JobMatchSerializer,
    JobPostingSerializer,
    JobSourceSerializer,
    ProfileDocumentSerializer,
    ProfileFactSerializer,
    ResumeSerializer,
    ResumeTailorSerializer,
    RegistrationSerializer,
    SourceRunSerializer,
)
from .services import create_tailored_resume, dashboard, generate_strategy, import_job_posting, ingest_profile_document, recompute_match
from .tasks import execute_agent_run_task, execute_source_run_task, ingest_profile_document_task, recompute_all_matches_task, recompute_job_match_task


def enqueue_profile_ingestion(document: ProfileDocument) -> dict:
    publish_user_event(document.owner_id, 'profile_ingestion_queued', {'document_id': document.id})
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


class RegistrationView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                user = serializer.save()
        except IntegrityError:
            return Response(
                {'email': ['An account with this email already exists.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {'id': user.id, 'email': user.email},
        }, status=status.HTTP_201_CREATED)


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


class CandidateProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request):
        from .domain.profiles import candidate_profile

        return candidate_profile(request.user)

    def get(self, request):
        return Response(CandidateProfileSerializer(self.get_object(request)).data)

    def patch(self, request):
        profile = self.get_object(request)
        serializer = CandidateProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(last_reviewed_at=timezone.now())
        from .domain.profiles import compute_profile_completeness

        compute_profile_completeness(request.user)
        profile.refresh_from_db()
        publish_user_event(request.user.id, 'candidate_profile_updated', {'profile_id': profile.id})
        return Response(CandidateProfileSerializer(profile).data)


class CandidateOnboardingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .domain.profiles import candidate_profile, onboarding_snapshot

        snapshot = onboarding_snapshot(request.user)
        snapshot['profile'] = CandidateProfileSerializer(candidate_profile(request.user)).data
        return Response(snapshot)

    def post(self, request):
        from .domain.profiles import answer_onboarding, candidate_profile

        step = str(request.data.get('step', '')).strip()
        answers = request.data.get('answers') or {}
        if not step or not isinstance(answers, dict):
            return Response({'detail': 'A step and answer object are required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            snapshot = answer_onboarding(request.user, step=step, answers=answers)
        except (TypeError, ValueError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        snapshot['profile'] = CandidateProfileSerializer(candidate_profile(request.user)).data
        publish_user_event(request.user.id, 'candidate_onboarding_updated', {'step': step, 'next_step': snapshot['step']['id']})
        return Response(snapshot)


class CandidatePreferenceViewSet(OwnedViewSet):
    serializer_class = CandidatePreferenceSerializer
    queryset = CandidatePreference.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        category = self.request.query_params.get('category')
        return qs.filter(category=category) if category else qs


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
        fact.lifecycle = 'verified'
        fact.save(update_fields=['verified_by_user', 'lifecycle', 'updated_at'])
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
        run = SourceRun.objects.create(owner=request.user, source=source)
        source.last_status = 'queued'
        source.last_message = 'Discovery refresh queued.'
        source.save(update_fields=['last_status', 'last_message', 'updated_at'])
        publish_user_event(request.user.id, 'source_run_queued', {'source_run_id': run.id, 'source_id': source.id})
        try:
            task = execute_source_run_task.delay(run.id)
            payload = {'mode': 'async', 'task_id': task.id}
        except Exception:
            from .domain.sourcing import execute_source_run

            execute_source_run(run)
            payload = {'mode': 'sync'}
        return Response({**SourceRunSerializer(run).data, **payload}, status=status.HTTP_202_ACCEPTED)


class SourceRunViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = SourceRunSerializer
    queryset = SourceRun.objects.select_related('source').all()

    def get_queryset(self):
        return self.queryset.filter(owner=self.request.user)


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
        publish_user_event(request.user.id, 'match_recompute_queued', {'job_id': job.id})
        try:
            task = recompute_job_match_task.delay(job.id)
            return Response({'mode': 'async', 'task_id': task.id}, status=status.HTTP_202_ACCEPTED)
        except Exception:
            match = recompute_match(job)
            publish_user_event(request.user.id, 'match_recomputed', {'job_id': job.id, 'match_id': match.id, 'score': match.score, 'confidence': match.confidence})
            return Response({'mode': 'sync', 'match_id': match.id})

    @action(detail=True, methods=['post'])
    def create_application(self, request, pk=None):
        job = self.get_object()
        application, _ = Application.objects.get_or_create(
            owner=request.user,
            job=job,
            defaults={'status': 'saved', 'notes': ''},
        )
        return Response(ApplicationSerializer(application, context={'request': request}).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def request_preparation(self, request, pk=None):
        from .domain.orchestration import default_thread

        job = self.get_object()
        run = AgentRun.objects.create(
            owner=request.user,
            thread=default_thread(request.user),
            agent='documents',
            objective=f'Prepare application materials for {job.title}',
            input={'job_id': job.id, 'intent': 'prepare_materials'},
        )
        publish_user_event(request.user.id, 'agent_run_queued', {'run_id': run.id, 'agent': run.agent})
        try:
            task = execute_agent_run_task.delay(run.id)
            run.celery_task_id = task.id
            run.save(update_fields=['celery_task_id', 'updated_at'])
        except Exception:
            from .domain.orchestration import execute_agent_run

            execute_agent_run(run)
        return Response(AgentRunSerializer(run).data, status=status.HTTP_202_ACCEPTED)


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
        facts = list(ProfileFact.objects.filter(owner=request.user).order_by('-verified_by_user', 'fact_type', 'title')[:160])
        validate_resume_claims(resume, facts)
        publish_user_event(request.user.id, 'resume_tailoring_finished', {'resume_id': resume.id, 'job_id': resume.target_job_id})
        return Response(self.get_serializer(resume).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        resume = self.get_object()
        unsupported = (resume.validation or {}).get('unsupported_claims', [])
        if unsupported and not request.data.get('accept_risk'):
            return Response({'detail': 'Resolve unsupported claims or explicitly accept the risk.', 'unsupported_claims': unsupported}, status=status.HTTP_409_CONFLICT)
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

    @action(detail=True, methods=['post'])
    def export_pdf(self, request, pk=None):
        resume = self.get_object()
        artifact = render_pdf(
            owner=request.user,
            title=resume.title,
            markdown=resume.content_markdown,
            kind='resume',
            resume=resume,
            design=(resume.content_json or {}).get('design'),
        )
        artifact.file.open('rb')
        filename = Path(artifact.file.name).name
        return FileResponse(artifact.file, as_attachment=True, filename=filename, content_type=artifact.mime_type)


class CoverLetterViewSet(OwnedViewSet):
    serializer_class = CoverLetterSerializer
    queryset = CoverLetter.objects.select_related('target_job').all()

    def get_queryset(self):
        qs = super().get_queryset()
        job_id = self.request.query_params.get('job')
        return qs.filter(target_job_id=job_id) if job_id else qs

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        letter = self.get_object()
        unsupported = (letter.validation or {}).get('unsupported_claims', [])
        if unsupported and not request.data.get('accept_risk'):
            return Response({'detail': 'Resolve unsupported claims or explicitly accept the risk.'}, status=status.HTTP_409_CONFLICT)
        letter.approved = True
        letter.save(update_fields=['approved', 'updated_at'])
        return Response(self.get_serializer(letter).data)


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

    @action(detail=True, methods=['post'])
    def request_render(self, request, pk=None):
        from .domain.orchestration import default_thread

        application = self.get_object()
        cover_letter = CoverLetter.objects.filter(owner=request.user, target_job=application.job).order_by('-version').first()
        if not application.resume or not application.resume.approved or (cover_letter and not cover_letter.approved):
            return Response(
                {'detail': 'Approve the current resume and cover letter before rendering the final bundle.'},
                status=status.HTTP_409_CONFLICT,
            )
        run = AgentRun.objects.create(
            owner=request.user, thread=default_thread(request.user), agent='documents',
            objective=f'Render the approved application bundle for {application.job.title}',
            input={'application_id': application.id, 'intent': 'render_bundle'},
            status='waiting_approval',
        )
        approval = ApprovalRequest.objects.create(
            owner=request.user, run=run, kind='render_bundle', title='Render final PDF bundle',
            prompt='Render the current resume and cover letter into final PDF artifacts?',
            payload={'application_id': application.id},
        )
        return Response(ApprovalRequestSerializer(approval).data, status=status.HTTP_201_CREATED)


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

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        artifact = self.get_object()
        if not artifact.file:
            raise Http404('Artifact file is unavailable.')
        filename = Path(artifact.file.name).name
        return FileResponse(
            artifact.file.open('rb'),
            content_type=artifact.mime_type or mimetypes.guess_type(filename)[0] or 'application/octet-stream',
            as_attachment=False,
            filename=filename,
        )


class ConversationThreadViewSet(OwnedViewSet):
    serializer_class = ConversationThreadSerializer
    queryset = ConversationThread.objects.prefetch_related('messages').all()

    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        from .domain.orchestration import create_concierge_run, execute_agent_run

        thread = self.get_object()
        content = str(request.data.get('content', '')).strip()
        if not content:
            return Response({'content': ['This field is required.']}, status=status.HTTP_400_BAD_REQUEST)
        context = request.data.get('context')
        if not isinstance(context, dict):
            context = {}
        run = create_concierge_run(request.user, message=content, thread=thread, context=context)
        publish_user_event(request.user.id, 'agent_run_queued', {'run_id': run.id, 'agent': run.agent})
        try:
            task = execute_agent_run_task.delay(run.id)
            run.celery_task_id = task.id
            run.save(update_fields=['celery_task_id', 'updated_at'])
        except Exception:
            execute_agent_run(run)
        return Response(AgentRunSerializer(run).data, status=status.HTTP_202_ACCEPTED)


class AgentRunViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AgentRunSerializer
    queryset = AgentRun.objects.select_related('thread').prefetch_related('steps').all()

    def get_queryset(self):
        return self.queryset.filter(owner=self.request.user)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        run = self.get_object()
        if run.status not in {'succeeded', 'failed', 'cancelled'}:
            run.status = 'cancelled'
            run.completed_at = timezone.now()
            run.save(update_fields=['status', 'completed_at', 'updated_at'])
        return Response(self.get_serializer(run).data)


class ApprovalRequestViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ApprovalRequestSerializer
    queryset = ApprovalRequest.objects.select_related('run').all()

    def get_queryset(self):
        qs = self.queryset.filter(owner=self.request.user)
        status_value = self.request.query_params.get('status')
        return qs.filter(status=status_value) if status_value else qs

    @action(detail=True, methods=['post'])
    def decide(self, request, pk=None):
        from .domain.orchestration import decide_approval

        approval = self.get_object()
        approved = request.data.get('approved') is True
        decide_approval(approval, approved=approved, response=request.data.get('response') or {})
        return Response(self.get_serializer(approval).data)


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(dashboard(request.user))


class TodayView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .domain.briefing import today_briefing

        return Response(today_briefing(request.user))


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
