# Integrate Client CLI Auth

## Why

The `browse` command cannot work with workers that require TOTP authentication - it lacks the AUTH_* message handling that `client-train` and `client-track` already have. Additionally, all client CLI commands still use Cognito anonymous signin instead of the new GitHub OAuth JWT + stored credentials system. This blocks users from testing the browse feature and prevents the full auth integration from being complete.

## What Changes

### Authentication (update)

Add requirements for client commands to use stored JWT credentials from the credentials file, falling back to Cognito for backward compatibility.

### CLI (update)

Add requirements for the `browse` command to implement P2P TOTP authentication, matching the existing pattern in `client-train` and `client-track`.
