import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { AuthService } from './auth.service';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const token = localStorage.getItem('job_search_studio_access') || '';
  if (!token) {
    return next(req).pipe(
      catchError((error) => {
        if (error.status === 401 && !req.url.includes('/auth/login/')) {
          auth.logout();
          router.navigate(['/login']);
        }
        return throwError(() => error);
      }),
    );
  }
  const authedRequest = req.clone({
    setHeaders: {
      Authorization: `Bearer ${token}`,
    },
  });
  return next(authedRequest).pipe(
    catchError((error) => {
      if (error.status === 401 && !req.url.includes('/auth/login/')) {
        auth.logout();
        router.navigate(['/login']);
      }
      return throwError(() => error);
    }),
  );
};
