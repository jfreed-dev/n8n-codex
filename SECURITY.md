# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly:

1. **Do not** open a public GitHub issue for security vulnerabilities
2. Email the maintainer directly at the email listed in the git commit history
3. Include a detailed description of the vulnerability and steps to reproduce

You can expect:
- Acknowledgment within 48 hours
- Regular updates on the fix progress
- Credit in the security advisory (if desired)

## Security Best Practices for Deployment

### Secrets Management

- **Never commit `.env` files** - use `.env.example` as a template
- Store secrets using environment variables or a secrets manager
- Rotate API keys and tokens regularly
- Use strong, unique passwords for all services

### Network Security

- Run n8n behind a reverse proxy (Traefik, Caddy, nginx) with HTTPS
- Do not expose n8n directly to the internet without authentication
- Use firewall rules to restrict access to internal services
- The Claude Agent API (port 8080) should not be publicly accessible

### UniFi Controller Access

- Use a dedicated read-only API user when possible
- For write operations, use credentials with minimal required permissions
- Enable MFA on your UniFi controller

### Docker Security

- Keep Docker and images updated
- Run containers as non-root when possible
- Use Docker secrets for sensitive values in production
- Review and pin image versions for production deployments

## Dependencies

This project uses third-party dependencies. Security updates are applied as they become available. Run `docker compose pull` regularly to get the latest images.
