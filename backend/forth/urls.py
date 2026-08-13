from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from core.views import (
    AgentRunViewSet,
    ApplicationEventViewSet,
    ApplicationViewSet,
    ApprovalRequestViewSet,
    ArtifactViewSet,
    CandidatePreferenceViewSet,
    CandidateOnboardingView,
    CandidateProfileView,
    ConversationThreadViewSet,
    CoverLetterViewSet,
    DashboardView,
    FrontendAppView,
    JobMatchViewSet,
    JobPostingViewSet,
    JobSourceViewSet,
    ProfileDocumentViewSet,
    ProfileFactViewSet,
    ResumeViewSet,
    SourceRunViewSet,
    StrategyView,
    TodayView,
)

router = DefaultRouter()
router.register('profile/documents', ProfileDocumentViewSet, basename='profile-document')
router.register('profile/facts', ProfileFactViewSet, basename='profile-fact')
router.register('profile/preferences', CandidatePreferenceViewSet, basename='candidate-preference')
router.register('sources', JobSourceViewSet, basename='job-source')
router.register('source-runs', SourceRunViewSet, basename='source-run')
router.register('jobs', JobPostingViewSet, basename='job')
router.register('matches', JobMatchViewSet, basename='job-match')
router.register('resumes', ResumeViewSet, basename='resume')
router.register('cover-letters', CoverLetterViewSet, basename='cover-letter')
router.register('applications', ApplicationViewSet, basename='application')
router.register('application-events', ApplicationEventViewSet, basename='application-event')
router.register('artifacts', ArtifactViewSet, basename='artifact')
router.register('conversations', ConversationThreadViewSet, basename='conversation-thread')
router.register('agent-runs', AgentRunViewSet, basename='agent-run')
router.register('approvals', ApprovalRequestViewSet, basename='approval-request')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/dashboard/', DashboardView.as_view(), name='dashboard'),
    path('api/today/', TodayView.as_view(), name='today'),
    path('api/profile/', CandidateProfileView.as_view(), name='candidate-profile'),
    path('api/profile/onboarding/', CandidateOnboardingView.as_view(), name='candidate-onboarding'),
    path('api/strategy/', StrategyView.as_view(), name='strategy'),
    path('api/', include(router.urls)),
    path('', FrontendAppView.as_view(), name='app'),
    path('<path:path>', FrontendAppView.as_view(), name='app-path'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
