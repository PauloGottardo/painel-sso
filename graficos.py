"""Gráficos de barras do painel, sempre com rótulo de dados (valores nas barras)."""
import plotly.express as px


def barras(*args, **kwargs):
    kwargs.setdefault("text_auto", True)
    fig = px.bar(*args, **kwargs)
    fig.update_traces(textposition="auto", cliponaxis=False)
    return fig