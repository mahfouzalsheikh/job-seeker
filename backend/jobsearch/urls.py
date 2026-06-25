from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from core.views import (
    ApplicationEventViewSet,
    ApplicationViewSet,
    ArtifactViewSet,
    DashboardView,
    FrontendAppView,
    JobMatchViewSet,
    JobPostingViewSet,
    JobSourceViewSet,
    ProfileDocumentViewSet,
    ProfileFactViewSet,
    ResumeViewSet,
    StrategyView,
)

router = DefaultRouter()
router.register('profile/documents', ProfileDocumentViewSet, basename='profile-document')
router.register('profile/facts', ProfileFactViewSet, basename='profile-fact')
router.register('sources', JobSourceViewSet, basename='job-source')
router.register('jobs', JobPostingViewSet, basename='job')
router.register('matches', JobMatchViewSet, basename='job-match')
router.register('resumes', ResumeViewSet, basename='resume')
router.register('applications', ApplicationViewSet, basename='application')
router.register('application-events', ApplicationEventViewSet, basename='application-event')
router.register('artifacts', ArtifactViewSet, basename='artifact')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/dashboard/', DashboardView.as_view(), name='dashboard'),
    path('api/strategy/', StrategyView.as_view(), name='strategy'),
    path('api/', include(router.urls)),
    path('', FrontendAppView.as_view(), name='app'),
    path('<path:path>', FrontendAppView.as_view(), name='app-path'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
