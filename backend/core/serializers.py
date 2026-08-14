from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from .models import (
    AgentRun,
    AgentStep,
    Application,
    ApplicationEvent,
    ApprovalRequest,
    Artifact,
    CandidatePreference,
    CandidateProfile,
    ConversationMessage,
    ConversationThread,
    CoverLetter,
    JobMatch,
    JobPosting,
    JobPostingVersion,
    JobRequirement,
    JobSource,
    MatchSignal,
    ProfileChunk,
    ProfileDocument,
    ProfileFact,
    Resume,
    ResumeClaim,
    SourceRun,
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


class RegistrationSerializer(serializers.Serializer):
    # Django's default username field is 150 characters; signup stores the
    # normalized email there so the same value can be used at sign-in.
    email = serializers.EmailField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False, style={'input_type': 'password'})

    def validate_email(self, value):
        email = value.strip().lower()
        User = get_user_model()
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return email

    def validate(self, attrs):
        User = get_user_model()
        candidate = User(username=attrs['email'], email=attrs['email'])
        try:
            validate_password(attrs['password'], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'password': list(exc.messages)}) from exc
        return attrs

    def create(self, validated_data):
        User = get_user_model()
        email = validated_data['email']
        return User.objects.create_user(username=email, email=email, password=validated_data['password'])


class ProfileDocumentSerializer(serializers.ModelSerializer):
    RESUME_EXTENSIONS = {'.pdf', '.doc', '.docx', '.html', '.htm', '.txt', '.md', '.rtf', '.odt'}

    class Meta:
        model = ProfileDocument
        fields = [
            'id', 'kind', 'title', 'upload', 'raw_text', 'status', 'status_message',
            'metadata', 'created_at', 'updated_at',
        ]
        read_only_fields = ['status', 'status_message', 'metadata', 'created_at', 'updated_at']

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs.get('kind', getattr(self.instance, 'kind', 'note')) != 'resume':
            return attrs
        upload = attrs.get('upload')
        raw_text = str(attrs.get('raw_text', '') or '').strip()
        if not upload and not raw_text:
            raise serializers.ValidationError({'upload': 'Upload your current resume or paste its text.'})
        if upload:
            from pathlib import Path

            suffix = Path(upload.name).suffix.lower()
            if suffix not in self.RESUME_EXTENSIONS:
                supported = ', '.join(sorted(self.RESUME_EXTENSIONS))
                raise serializers.ValidationError({'upload': f'Unsupported resume format. Use one of: {supported}.'})
            if upload.size > 15 * 1024 * 1024:
                raise serializers.ValidationError({'upload': 'Resume files must be 15 MB or smaller.'})
        return attrs


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
            'verified_by_user', 'lifecycle', 'evidence_quote', 'strength',
            'started_on', 'ended_on', 'user_notes', 'metadata', 'created_at', 'updated_at',
        ]
        read_only_fields = ['source_document', 'source_document_title', 'source_chunk', 'metadata', 'created_at', 'updated_at']


class CandidateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CandidateProfile
        fields = [
            'id', 'headline', 'professional_summary', 'target_roles', 'target_industries',
            'location', 'authorized_countries', 'work_modes', 'employment_types',
            'minimum_compensation', 'compensation_currency', 'excluded_companies',
            'completeness', 'last_reviewed_at', 'onboarding_state',
            'onboarding_completed_at', 'embedding_model', 'embedding_provider',
            'embedding_updated_at', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'completeness', 'last_reviewed_at', 'onboarding_state',
            'onboarding_completed_at', 'embedding_model', 'embedding_provider',
            'embedding_updated_at', 'created_at', 'updated_at',
        ]


class CandidatePreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CandidatePreference
        fields = [
            'id', 'category', 'label', 'value', 'importance', 'verified_by_user',
            'rationale', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class JobSourceSerializer(serializers.ModelSerializer):
    job_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = JobSource
        fields = [
            'id', 'kind', 'name', 'config', 'enabled', 'last_run_at',
            'last_status', 'last_message', 'job_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['last_run_at', 'last_status', 'last_message', 'job_count', 'created_at', 'updated_at']


class SourceRunSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(source='source.name', read_only=True)

    class Meta:
        model = SourceRun
        fields = [
            'id', 'source', 'source_name', 'status', 'started_at', 'completed_at',
            'discovered_count', 'imported_count', 'updated_count', 'skipped_count',
            'error_count', 'cursor', 'log', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class JobRequirementSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobRequirement
        fields = ['id', 'kind', 'category', 'text', 'normalized_value', 'is_hard', 'weight', 'metadata']
        read_only_fields = fields


class JobPostingVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobPostingVersion
        fields = ['id', 'version', 'content_hash', 'extracted_json', 'fetched_at', 'is_current']
        read_only_fields = fields


class MatchSignalSerializer(serializers.ModelSerializer):
    class Meta:
        model = MatchSignal
        fields = ['id', 'kind', 'label', 'score', 'weight', 'explanation', 'evidence']
        read_only_fields = fields


class JobMatchSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(source='job.title', read_only=True)
    company = serializers.CharField(source='job.company', read_only=True)
    signals = MatchSignalSerializer(many=True, read_only=True)

    class Meta:
        model = JobMatch
        fields = [
            'id', 'job', 'job_title', 'company', 'score', 'hard_filter_status',
            'explanation_json', 'missing_requirements', 'supporting_facts',
            'confidence', 'computed_at', 'created_at', 'updated_at',
            'signals',
        ]
        read_only_fields = fields


class JobPostingSerializer(OwnerScopedRelationsMixin, serializers.ModelSerializer):
    match = JobMatchSerializer(read_only=True)
    owner_related_fields = {'source': JobSource}
    requirements = JobRequirementSerializer(many=True, read_only=True)
    versions = JobPostingVersionSerializer(many=True, read_only=True)

    class Meta:
        model = JobPosting
        fields = [
            'id', 'source', 'title', 'company', 'location', 'remote_policy',
            'seniority', 'compensation', 'description_text', 'extracted_json',
            'source_url', 'application_url', 'status', 'posted_at',
            'canonical_url', 'source_external_id', 'last_seen_at', 'expires_at',
            'freshness_status', 'discovered_at', 'created_at', 'updated_at', 'match',
            'requirements', 'versions', 'embedding_model', 'embedding_provider',
            'embedding_updated_at',
        ]
        read_only_fields = [
            'extracted_json', 'discovered_at', 'created_at', 'updated_at', 'match',
            'embedding_model', 'embedding_provider', 'embedding_updated_at',
        ]


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
        read_only_fields = ['validation', 'approved', 'claims', 'created_at', 'updated_at']


class CoverLetterSerializer(OwnerScopedRelationsMixin, serializers.ModelSerializer):
    target_job_title = serializers.CharField(source='target_job.title', read_only=True)
    owner_related_fields = {'target_job': JobPosting}

    class Meta:
        model = CoverLetter
        fields = [
            'id', 'title', 'target_job', 'target_job_title', 'content_markdown',
            'content_json', 'validation', 'approved', 'version', 'created_at', 'updated_at',
        ]
        read_only_fields = ['validation', 'version', 'created_at', 'updated_at']


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
    owner_related_fields = {'application': Application, 'resume': Resume, 'cover_letter': CoverLetter}

    class Meta:
        model = Artifact
        fields = [
            'id', 'application', 'resume', 'cover_letter', 'kind', 'title', 'file_url',
            'content_text', 'metadata', 'version', 'content_hash', 'mime_type', 'approved',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['metadata', 'file_url', 'created_at', 'updated_at']

    def get_file_url(self, obj: Artifact) -> str:
        if not obj.file:
            return ''
        request = self.context.get('request')
        url = f'/api/artifacts/{obj.pk}/download/'
        return request.build_absolute_uri(url) if request else url


class AgentStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentStep
        fields = ['id', 'sequence', 'kind', 'name', 'status', 'input', 'output', 'error', 'started_at', 'completed_at']
        read_only_fields = fields


class AgentRunSerializer(serializers.ModelSerializer):
    steps = AgentStepSerializer(many=True, read_only=True)

    class Meta:
        model = AgentRun
        fields = [
            'id', 'thread', 'agent', 'objective', 'status', 'input', 'output', 'error',
            'idempotency_key', 'celery_task_id', 'started_at', 'completed_at', 'model',
            'usage', 'steps', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class ApprovalRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalRequest
        fields = ['id', 'run', 'kind', 'title', 'prompt', 'payload', 'status', 'response', 'decided_at', 'created_at', 'updated_at']
        read_only_fields = fields


class ConversationMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConversationMessage
        fields = ['id', 'thread', 'role', 'content', 'metadata', 'created_at']
        read_only_fields = fields


class ConversationThreadSerializer(serializers.ModelSerializer):
    messages = ConversationMessageSerializer(many=True, read_only=True)

    class Meta:
        model = ConversationThread
        fields = ['id', 'title', 'status', 'context', 'messages', 'created_at', 'updated_at']
        read_only_fields = ['messages', 'created_at', 'updated_at']


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
        resume = attrs.get('resume', getattr(self.instance, 'resume', None))
        if status == 'applied' and (resume is None or not resume.approved):
            raise serializers.ValidationError({'status': 'Approve the resume used for this application before marking it applied.'})
        if status == 'applied' and not attrs.get('applied_at') and not getattr(self.instance, 'applied_at', None):
            attrs['applied_at'] = timezone.now()
        return attrs
