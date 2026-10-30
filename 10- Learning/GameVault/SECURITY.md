# Security

Report security issues privately to the repository owner rather than opening a public issue containing exploit details or personal data.

Rotate `COLLECTOR_TOKEN` and provider API keys if they are exposed. Keep PostgreSQL on a private network, publish the API only behind HTTPS, and give Power BI a read-only database login limited to the `powerbi` schema.
