from .analysis import sync_analysis_jobs


def get_deployments():
    return [
        sync_analysis_jobs.to_deployment(name="sync-analysis-jobs", cron="*/15 * * * *")
    ]
