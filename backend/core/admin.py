from django.contrib import admin

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
    OnboardingResponse,
    ProfileChunk,
    ProfileDocument,
    ProfileFact,
    Resume,
    ResumeClaim,
    SourceRun,
)


@admin.register(ProfileDocument)
class ProfileDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'kind', 'owner', 'status', 'updated_at')
    list_filter = ('kind', 'status')
    search_fields = ('title', 'raw_text')


@admin.register(ProfileFact)
class ProfileFactAdmin(admin.ModelAdmin):
    list_display = ('title', 'fact_type', 'owner', 'confidence', 'verified_by_user')
    list_filter = ('fact_type', 'verified_by_user', 'confidence')
    search_fields = ('title', 'statement')


@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'owner', 'remote_policy', 'status', 'discovered_at')
    list_filter = ('remote_policy', 'status')
    search_fields = ('title', 'company', 'description_text')


@admin.register(JobMatch)
class JobMatchAdmin(admin.ModelAdmin):
    list_display = ('job', 'score', 'confidence', 'computed_at')
    list_filter = ('confidence',)


admin.site.register(ProfileChunk)
admin.site.register(JobSource)
admin.site.register(Resume)
admin.site.register(ResumeClaim)
admin.site.register(Application)
admin.site.register(ApplicationEvent)
admin.site.register(Artifact)
admin.site.register(CandidateProfile)
admin.site.register(CandidatePreference)
admin.site.register(OnboardingResponse)
admin.site.register(SourceRun)
admin.site.register(JobPostingVersion)
admin.site.register(JobRequirement)
admin.site.register(CoverLetter)
admin.site.register(ConversationThread)
admin.site.register(ConversationMessage)
admin.site.register(AgentRun)
admin.site.register(AgentStep)
admin.site.register(ApprovalRequest)
