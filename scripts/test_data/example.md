# Authentication System

This document explains how the authentication system works in our application.

## Overview

The authentication system provides secure user login and session management.
It supports multiple authentication methods including password-based and OAuth2.

## Login Flow

Users authenticate via the `/api/login` endpoint. The process involves:

1. User submits credentials (email + password)
2. Server validates credentials against the database
3. On success, a JWT token is generated
4. Token is returned to the client

### Password Validation

Passwords must meet the following requirements:
- Minimum 8 characters
- At least one uppercase letter
- At least one number

### Token Generation

Tokens are generated using the HS256 algorithm with a secret key.
Each token contains the user ID and expiration timestamp.

## Session Management

Sessions are stored in Redis with a 24-hour TTL (time to live).

### Session Structure

Each session contains:
- User ID
- Creation timestamp
- Last activity timestamp
- IP address

### Token Refresh

When tokens expire, the client can request a refresh using the `/api/refresh` endpoint.
The refresh token has a longer validity period (7 days).

## Security Considerations

- All passwords are hashed using bcrypt
- Rate limiting is applied to login endpoints
- Failed login attempts are logged for security monitoring

## API Reference

### POST /api/login

Authenticate a user and return a token.

**Request:**
```json
{
    "email": "user@example.com",
    "password": "secretpassword"
}
```

**Response:**
```json
{
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "expiresIn": 3600
}
```

### POST /api/logout

Invalidate the current session.

### POST /api/refresh

Get a new access token using the refresh token.
