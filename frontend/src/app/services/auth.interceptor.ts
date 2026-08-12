import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, switchMap, throwError } from 'rxjs';
import { AuthService } from './auth.service';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const token = localStorage.getItem('job_search_studio_access') || '';
  const isAuthRequest = req.url.includes('/auth/login/') || req.url.includes('/auth/refresh/');
  const recover = (error: any) => {
    if (error.status !== 401 || isAuthRequest || !auth.getRefreshToken()) {
      if (error.status === 401 && !isAuthRequest) {
        auth.logout();
        router.navigate(['/login']);
      }
      return throwError(() => error);
    }
    return auth.refresh().pipe(
      switchMap(({ access }) => next(req.clone({
        setHeaders: { Authorization: `Bearer ${access}` },
      }))),
      catchError((refreshError) => {
        auth.logout();
        router.navigate(['/login']);
        return throwError(() => refreshError);
      }),
    );
  };
  if (!token) {
    return next(req).pipe(catchError(recover));
  }
  const authedRequest = req.clone({
    setHeaders: {
      Authorization: `Bearer ${token}`,
    },
  });
  return next(authedRequest).pipe(catchError(recover));
};
