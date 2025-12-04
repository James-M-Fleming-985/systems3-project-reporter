# Custom Metrics Storage

This directory contains server-side persisted custom metrics for projects.

Each project's metrics are stored in a separate YAML file named:
`{project_name}_metrics.yaml`

## Format

```yaml
project_name: "Project Name"
last_updated: "2025-12-04T10:00:00"
metrics:
  - name: "OEE"
    value: 85.5
    target: 95.0
    targetDate: "2026-01-31"
    unit: "%"
    lastUpdated: "2025-12-04T10:00:00"
    history:
      - value: 85.5
        date: "2025-12-04T10:00:00"
```

## Benefits

- ✅ Persists across browser sessions
- ✅ Persists across deployments
- ✅ Persists across cache clears
- ✅ Accessible from any browser
- ✅ Backed up with Railway volumes
