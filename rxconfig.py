import reflex as rx

config = rx.Config(
    app_name="POLY_PROJECT",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)