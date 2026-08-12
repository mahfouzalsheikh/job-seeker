from __future__ import annotations

from django.utils import timezone
from rest_framework import serializers

from .models import (
    Application,
    ApplicationEvent,
    Artifact,
    JobMatch,
    JobPosting,
    JobSource,
    ProfileChunk,
    ProfileDocument,
    ProfileFact,
    Resume,
    ResumeClaim,
)


class OwnerScopedRelationsMixin:
    owner_related_fields: dict[str, type] = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        owner = getattr(request, 'user', None)
        authenticated = bool(owner and owner.is_authenticated)
        for field_name, model in self.owner_related_fields.items():
            field = self.fields.get(field_name)
            if field is not None and hasattr(field, 'queryset'):
                field.queryset = model.objects.filter(owner=owner) if authenticated else model.objects.none()


class ProfileDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfileDocument
        fields = [
            'id', 'kind', 'title', 'upload', 'raw_text', 'status', 'status_message',
            'metadata', 'created_at', 'updated_at',
        ]
        read_only_fields = ['status', 'status_message', 'metadata', 'created_at', 'updated_at']


class ProfileChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfileChunk
        fields = ['id', 'document', 'text', 'token_count', 'metadata', 'created_at']
        read_only_fields = ['token_count', 'metadata', 'created_at']


class ProfileFactSerializer(serializers.ModelSerializer):
    source_document_title = serializers.CharField(source='source_document.title', read_only=True)

    class Meta:
        model = ProfileFact
        fields = [
            'id', 'fact_type', 'title', 'statement', 'normalized_value', 'confidence',
            'source_document', 'source_document_title', 'source_chunk',
            'verified_by_user', 'metadata', 'created_at', 'updated_at',
        ]
        read_only_fields = ['source_document', 'source_document_title', 'source_chunk', 'metadata', 'created_at', 'updated_at']


class JobSourceSerializer(serializers.ModelSerializer):
    job_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = JobSource
        fields = [
            'id', 'kind', 'name', 'config', 'enabled', 'last_run_at',
            'last_status', 'last_message', 'job_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['last_run_at', 'last_status', 'last_message', 'job_count', 'created_at', 'updated_at']


class JobMatchSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(source='job.title', read_only=True)
    company = serializers.CharField(source='job.company', read_only=True)

    class Meta:
        model = JobMatch
        fields = [
            'id', 'job', 'job_title', 'company', 'score', 'hard_filter_status',
            'explanation_json', 'missing_requirements', 'supporting_facts',
            'confidence', 'computed_at', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class JobPostingSerializer(OwnerScopedRelationsMixin, serializers.ModelSerializer):
    match = JobMatchSerializer(read_only=True)
    owner_related_fields = {'source': JobSource}

    class Meta:
        model = JobPosting
        fields = [
            'id', 'source', 'title', 'company', 'location', 'remote_policy',
            'seniority', 'compensation', 'description_text', 'extracted_json',
            'source_url', 'application_url', 'status', 'posted_at',
            'discovered_at', 'created_at', 'updated_at', 'match',
        ]
        read_only_fields = ['extracted_json', 'discovered_at', 'created_at', 'updated_at', 'match']


class JobImportSerializer(serializers.Serializer):
    text = serializers.CharField()
    source_url = serializers.URLField(required=False, allow_blank=True)
    source = serializers.PrimaryKeyRelatedField(queryset=JobSource.objects.none(), required=False, allow_null=True)

    def __init__(self, *args, **kwargs):
        owner = kwargs.pop('owner', None)
        super().__init__(*args, **kwargs)
        if owner is not None:
            self.fields['source'].queryset = JobSource.objects.filter(owner=owner)


class ResumeClaimSerializer(serializers.ModelSerializer):
    profile_fact_title = serializers.CharField(source='profile_fact.title', read_only=True)

    class Meta:
        model = ResumeClaim
        fields = ['id', 'text', 'profile_fact', 'profile_fact_title', 'support_status', 'created_at']
        read_only_fields = ['created_at']


class ResumeSerializer(OwnerScopedRelationsMixin, serializers.ModelSerializer):
    target_job_title = serializers.CharField(source='target_job.title', read_only=True)
    claims = ResumeClaimSerializer(many=True, read_only=True)
    owner_related_fields = {'parent_resume': Resume, 'target_job': JobPosting}

    class Meta:
        model = Resume
        fields = [
            'id', 'kind', 'title', 'content_markdown', 'content_json',
            'parent_resume', 'target_job', 'target_job_title', 'validation',
            'approved', 'claims', 'created_at', 'updated_at',
        ]
        read_only_fields = ['validation', 'claims', 'created_at', 'updated_at']


class ResumeTailorSerializer(serializers.Serializer):
    job = serializers.PrimaryKeyRelatedField(queryset=JobPosting.objects.none())
    canonical_resume = serializers.PrimaryKeyRelatedField(queryset=Resume.objects.none(), required=False, allow_null=True)

    def __init__(self, *args, **kwargs):
        owner = kwargs.pop('owner', None)
        super().__init__(*args, **kwargs)
        if owner is not None:
            self.fields['job'].queryset = JobPosting.objects.filter(owner=owner)
            self.fields['canonical_resume'].queryset = Resume.objects.filter(owner=owner, kind='canonical')


class ApplicationEventSerializer(OwnerScopedRelationsMixin, serializers.ModelSerializer):
    owner_related_fields = {'application': Application}

    class Meta:
        model = ApplicationEvent
        fields = ['id', 'application', 'event_type', 'happened_at', 'notes', 'metadata', 'created_at']
        read_only_fields = ['metadata', 'created_at']


class ArtifactSerializer(OwnerScopedRelationsMixin, serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    owner_related_fields = {'application': Application, 'resume': Resume}

    class Meta:
        model = Artifact
        fields = [
            'id', 'application', 'resume', 'kind', 'title', 'file', 'file_url',
            'content_text', 'metadata', 'created_at', 'updated_at',
        ]
        read_only_fields = ['metadata', 'file_url', 'created_at', 'updated_at']

    def get_file_url(self, obj: Artifact) -> str:
        if not obj.file:
            return ''
        request = self.context.get('request')
        url = obj.file.url
        return request.build_absolute_uri(url) if request else url


class ApplicationSerializer(OwnerScopedRelationsMixin, serializers.ModelSerializer):
    job_detail = JobPostingSerializer(source='job', read_only=True)
    resume_title = serializers.CharField(source='resume.title', read_only=True)
    events = ApplicationEventSerializer(many=True, read_only=True)
    artifacts = ArtifactSerializer(many=True, read_only=True)
    owner_related_fields = {'job': JobPosting, 'resume': Resume}

    class Meta:
        model = Application
        fields = [
            'id', 'job', 'job_detail', 'status', 'resume', 'resume_title',
            'applied_at', 'follow_up_at', 'outcome', 'notes',
            'contact_name', 'contact_email', 'events', 'artifacts',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['events', 'artifacts', 'created_at', 'updated_at']

    def validate(self, attrs):
        status = attrs.get('status', getattr(self.instance, 'status', None))
        if status == 'applied' and not attrs.get('applied_at') and not getattr(self.instance, 'applied_at', None):
            attrs['applied_at'] = timezone.now()
        return attrs
