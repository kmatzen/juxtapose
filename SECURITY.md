# Security Features

This document outlines the security measures implemented to protect survey data and prevent unauthorized access.

## Overview

The survey application implements multiple layers of security to protect against:
- **Data Leakage**: Preventing unauthorized access to participant data
- **Malicious Deletions**: Protecting against unauthorized data deletion
- **Brute Force Attacks**: Rate limiting to prevent password guessing
- **CSRF Attacks**: Cross-Site Request Forgery protection on admin endpoints
- **Session Hijacking**: Secure session configuration
- **Information Disclosure**: Sanitized error messages

---

## Security Features

### 1. **Authentication & Authorization**

#### Admin Password Protection
- **Requirement**: Admin panel requires password authentication
- **Configuration**: Set via `ADMIN_PASSWORD` environment variable
- **Warning**: Application warns if default password is used in production
- **Session Management**: Admin sessions expire after 2 hours of inactivity

#### Session Security
- `SESSION_COOKIE_SECURE`: Cookies only sent over HTTPS (production)
- `SESSION_COOKIE_HTTPONLY`: Prevents JavaScript access to session cookies
- `SESSION_COOKIE_SAMESITE='Lax'`: Prevents CSRF attacks
- `PERMANENT_SESSION_LIFETIME`: 2-hour timeout (admin sessions only)

**Note**: Regular survey participants have sessions that last until browser close (no timeout). Only admin sessions have the 2-hour inactivity timeout. This ensures users can complete surveys at their own pace without losing progress.

### 2. **CSRF (Cross-Site Request Forgery) Protection**

#### Admin Endpoints (CSRF Protected)
- `/api/admin/delete_by_email` - DELETE operations require CSRF token
- CSRF tokens are generated per-session and validated on each request
- Invalid CSRF tokens result in 400 Bad Request

#### Survey Endpoints (CSRF Exempt)
- `/api/submit_demographics` - Protected by session validation
- `/api/submit_survey` - Protected by session validation
- GET endpoints are automatically exempt from CSRF

### 3. **Rate Limiting**

Prevents brute force and DoS attacks:

| Endpoint | Limit | Purpose |
|----------|-------|---------|
| `/admin/login` | 10 per hour | Prevent password guessing |
| `/api/admin/delete_by_email` | 20 per hour | Prevent mass deletion abuse |
| All other endpoints | 200 per hour | General DoS protection |

### 4. **Audit Logging**

All security-sensitive actions are logged to `audit.log`:

#### Logged Actions
- `ADMIN_LOGIN_SUCCESS` - Successful admin login
- `ADMIN_LOGIN_FAILED` - Failed login attempt
- `ADMIN_LOGOUT` - Admin logout
- `DELETE_SUCCESS` - Successful data deletion
- `DELETE_FAILED` - Failed deletion attempt
- `DELETE_NOT_FOUND` - Attempted deletion of non-existent email
- `DELETE_ERROR` - Deletion error

#### Log Format
```json
{
  "timestamp": "2025-11-15T10:30:00",
  "ip": "192.168.1.1",
  "session": "uuid-here",
  "role": "ADMIN",
  "action": "DELETE_SUCCESS",
  "details": {"email": "user@example.com", "responses_deleted": 30}
}
```

### 5. **HTTP Security Headers**

Added to all responses:
- `X-Content-Type-Options: nosniff` - Prevent MIME sniffing
- `X-Frame-Options: DENY` - Prevent clickjacking
- `X-XSS-Protection: 1; mode=block` - Enable XSS filtering
- `Referrer-Policy: strict-origin-when-cross-origin` - Control referrer info
- `Strict-Transport-Security` - Force HTTPS (production only)

### 6. **Input Validation**

#### Email Validation
- Format validation (must contain '@')
- Length validation (max 255 characters)
- Sanitization to prevent injection attacks

#### SQL Injection Prevention
- **Parameterized Queries**: All database queries use parameter binding
- **No String Interpolation**: Never concatenate user input into SQL

### 7. **Error Message Sanitization**

- **Internal Errors**: Never expose stack traces or database errors to clients
- **Generic Messages**: Users see "An error occurred" instead of specific error details
- **Server Logging**: Detailed errors logged server-side for debugging

### 8. **Secret Management**

#### Required Environment Variables (Production)
- `SECRET_KEY`: **REQUIRED** - Flask session encryption key
- `ADMIN_PASSWORD`: Recommended to change from default
- `REFERRAL_CODES`: Optional - Survey access codes

#### Validation
- Application **refuses to start** if `SECRET_KEY` is not set in production
- Warns if default `ADMIN_PASSWORD` is used in production

---

## Deployment Security Checklist

Before deploying to production:

- [ ] Set strong `SECRET_KEY` environment variable (use `python -c "import secrets; print(secrets.token_hex(32))"`)
- [ ] Set strong `ADMIN_PASSWORD` environment variable
- [ ] Verify HTTPS is enabled on hosting platform
- [ ] Review `audit.log` regularly for suspicious activity
- [ ] Set `FLASK_ENV=production` to enable HSTS and secure cookies
- [ ] Configure `REFERRAL_CODES` if you want to gate survey access
- [ ] Test rate limiting is working (try 11 failed logins in 1 hour)
- [ ] Verify CSRF protection (delete request should fail without token)

---

## Generating Strong Secrets

### SECRET_KEY
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### ADMIN_PASSWORD
```bash
python -c "import secrets; print(secrets.token_urlsafe(16))"
```

---

## Setting Environment Variables

### Fly.io
```bash
fly secrets set SECRET_KEY="your-secret-key-here"
fly secrets set ADMIN_PASSWORD="your-admin-password-here"
```

### Render.com
Set in dashboard: Settings → Environment → Environment Variables

### Local Development
Create `.env` file (add to `.gitignore`):
```
SECRET_KEY=dev-secret-key
ADMIN_PASSWORD=dev-admin-password
FLASK_ENV=development
```

---

## Monitoring & Response

### Check Audit Logs
```bash
# On Fly.io
fly ssh console -C "tail -f /data/audit.log"

# Locally
tail -f audit.log
```

### Analyze Failed Login Attempts
```bash
grep "ADMIN_LOGIN_FAILED" audit.log | jq '.ip' | sort | uniq -c | sort -rn
```

### Monitor Deletion Activity
```bash
grep "DELETE_SUCCESS" audit.log | jq '.details'
```

---

## Incident Response

If you suspect a security breach:

1. **Immediately rotate secrets**:
   ```bash
   fly secrets set SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
   fly secrets set ADMIN_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(16))')"
   ```

2. **Review audit logs** for unauthorized access:
   ```bash
   fly ssh console -C "cat /data/audit.log"
   ```

3. **Check for suspicious deletions**:
   ```bash
   grep "DELETE_" audit.log | jq '.'
   ```

4. **Reset admin sessions** (all admin users will need to re-login):
   ```bash
   fly apps restart survey-app-silent-frost-2723
   ```

---

## Security Limitations

### Known Limitations
1. **SQLite Database**: Database file is protected by filesystem permissions, but is not encrypted at rest
2. **IP-based Rate Limiting**: Can be bypassed with distributed attacks or proxies
3. **No Two-Factor Authentication**: Admin login uses single-factor password authentication
4. **Audit Log Rotation**: Audit logs grow indefinitely and are not automatically rotated
5. **No Email Verification**: Email addresses are not verified (only used for survey tracking)

### Recommendations for Enhanced Security
- Use PostgreSQL instead of SQLite for better concurrency and encryption options
- Implement 2FA for admin access using TOTP (e.g., Flask-Security)
- Set up log rotation and archival
- Implement email verification if collecting PII
- Use a dedicated secrets manager (e.g., HashiCorp Vault) for production
- Set up monitoring/alerting for suspicious activity (e.g., Sentry, DataDog)

---

## Contact

Security concerns: survey-x7qp@adobe.com

