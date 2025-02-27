from prefect.blocks.notifications import SlackWebhook


def notify_slack(message: str):
    slack_webhook = SlackWebhook.load("tmnl-slack-webhook")
    slack_webhook.notify(message)  # type: ignore[union-attr]
