import os
import inspect
import gradio as gr
from datasets import load_dataset
from huggingface_hub import InferenceClient

try:
    import spaces
except ImportError:
    class spaces:
        @staticmethod
        def GPU(func):
            return func


# ---------------------------------------------------------------------------
# Hotfix: Patch Gradio / Pydantic schema bug (TypeError: 'bool' is not iterable)
# In Pydantic 2.11+, 'additionalProperties: False' produces a boolean schema,
# which causes gradio_client.utils.get_type() to fail on `"const" in False`.
# ---------------------------------------------------------------------------
try:
    import gradio_client.utils as gc_utils

    if hasattr(gc_utils, "_json_schema_to_python_type"):
        _orig_json_schema = gc_utils._json_schema_to_python_type
        def _safe_json_schema(schema, *args, **kwargs):
            if isinstance(schema, bool):
                return "bool"
            return _orig_json_schema(schema, *args, **kwargs)
        gc_utils._json_schema_to_python_type = _safe_json_schema

    if hasattr(gc_utils, "get_type"):
        _orig_get_type = gc_utils.get_type
        def _safe_get_type(schema, *args, **kwargs):
            if isinstance(schema, bool):
                return "boolean"
            return _orig_get_type(schema, *args, **kwargs)
        gc_utils.get_type = _safe_get_type
except Exception as patch_err:
    print(f"Warning: could not apply schema patch: {patch_err}")

try:
    import gradio.routes as gr_routes
    if hasattr(gr_routes, "api_info"):
        _orig_api_info = gr_routes.api_info
        def _safe_api_info(*args, **kwargs):
            try:
                return _orig_api_info(*args, **kwargs)
            except Exception:
                return {"named_endpoints": {}, "unnamed_endpoints": {}}
        gr_routes.api_info = _safe_api_info
except Exception:
    pass

# 1. Connect to your live dataset
DATASET_ID = "Faraz-Ahmad/latent-space-podcast-archive"

episodes = {}
episode_titles = []

def load_archive(force_download=False):
    global episodes, episode_titles
    print(f"Loading archive from: {DATASET_ID} (force={force_download})...")
    try:
        kwargs = {"download_mode": "force_redownload"} if force_download else {}
        dataset = load_dataset(DATASET_ID, split="train", **kwargs)
        episodes = {row["episode_title"]: row for row in dataset}
        episode_titles = list(episodes.keys())
        print(f"[+] Loaded {len(episodes)} episodes successfully!")
    except Exception as e:
        print(f"Error loading dataset: {e}")
        if not episodes:
            episodes = {}
            episode_titles = ["No episodes found"]
    return episode_titles

# Initial load on startup
load_archive(force_download=False)

# 2. Setup AI Client
HF_TOKEN = os.environ.get("HF_TOKEN")
client = InferenceClient(token=HF_TOKEN)

# Pre-extract initial episode for default UI view
first_ep = episodes[episode_titles[0]] if episode_titles and episode_titles[0] in episodes else {}
initial_date = first_ep.get("published_date", "")
initial_audio = f'<audio controls style="width: 100%;"><source src="{first_ep.get("audio_url", "")}" type="audio/mpeg"></audio>' if first_ep.get("audio_url") else ""
initial_briefing = first_ep.get("intel_briefing", "No briefing available.")

# -------------------------------------------------------------
# Function A: Answering User Questions (RAG Engine)
# -------------------------------------------------------------
@spaces.GPU
def chat_with_archive(user_question, selected_episode, chat_history):
    if not user_question or not user_question.strip():
        return chat_history, ""

    if chat_history is None:
        chat_history = []

    # Pull context from the selected episode
    if selected_episode in episodes:
        target = episodes[selected_episode]
        context = f"Episode: {target['episode_title']}\nPublished: {target['published_date']}\n\nBriefing & Key Insights:\n{target['intel_briefing'][:3000]}"
    elif episode_titles and episode_titles[0] in episodes:
        current_first = episodes[episode_titles[0]]
        context = f"Episode: {current_first.get('episode_title', '')}\nPublished: {current_first.get('published_date', '')}\n\nBriefing:\n{current_first.get('intel_briefing', '')[:3000]}"
    else:
        context = "No episode data available."

    system_prompt = (
        "You are an AI research assistant for the Latent Space podcast. "
        "Answer the user's question accurately using ONLY the provided podcast context. "
        "Cite specific details, technical trade-offs, and quotes where appropriate. "
        "Keep your response concise, clear, and formatted in markdown."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Context from Podcast:\n{context}\n\nQuestion: {user_question}"}
    ]

    try:
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.2-3B-Instruct",
            messages=messages,
            max_tokens=800,
            temperature=0.2
        )
        answer = response.choices[0].message.content
    except Exception:
        try:
            response = client.chat.completions.create(
                model="Qwen/Qwen2.5-72B-Instruct",
                messages=messages,
                max_tokens=800,
                temperature=0.2
            )
            answer = response.choices[0].message.content
        except Exception as err:
            answer = f"⚠️ Could not generate answer: {str(err)}"

    chat_history.append({"role": "user", "content": user_question})
    chat_history.append({"role": "assistant", "content": answer})
    return chat_history, ""

# -------------------------------------------------------------
# Function B: Episode Selector Callback
# -------------------------------------------------------------
def update_episode_view(selected_title):
    if selected_title in episodes:
        ep = episodes[selected_title]
        audio_html = f'<audio controls style="width: 100%;"><source src="{ep["audio_url"]}" type="audio/mpeg"></audio>'
        return ep["published_date"], audio_html, ep["intel_briefing"]
    return "", "", "No episode selected."

# Function C: Sync with Hugging Face Dataset Hub
def sync_archive():
    titles = load_archive(force_download=True)
    new_val = titles[0] if titles else None
    if new_val and new_val in episodes:
        ep = episodes[new_val]
        new_date = ep.get("published_date", "")
        new_audio = f'<audio controls style="width: 100%;"><source src="{ep.get("audio_url", "")}" type="audio/mpeg"></audio>' if ep.get("audio_url") else ""
        new_briefing = ep.get("intel_briefing", "No briefing available.")
    else:
        new_date, new_audio, new_briefing = "", "", "No episodes loaded."
    
    status_text = f"✅ **Synced with Hub!** {len(titles)} episode(s) available in archive."
    return (
        gr.update(choices=titles, value=new_val),
        gr.update(choices=titles, value=new_val),
        status_text,
        new_date,
        new_audio,
        new_briefing
    )

# -------------------------------------------------------------
# Gradio UI Layout
# -------------------------------------------------------------
with gr.Blocks(title="Latent Space Intel Hub") as demo:
    gr.Markdown("# 🎙️ Latent Space Podcast Intelligence Hub")
    gr.Markdown("Search, listen, and chat with technical insights extracted from the **Latent Space (The AI Engineer Podcast)** archive.")

    with gr.Row():
        archive_status = gr.Markdown(f"📦 **Archive Status:** {len(episode_titles)} episode(s) loaded from `{DATASET_ID}`")
        btn_sync = gr.Button("🔄 Sync Latest from Hub", size="sm", scale=0)

    with gr.Tabs():
        # TAB 1: Chatbot (RAG)
        with gr.TabItem("💬 Ask the Podcast"):
            with gr.Row():
                with gr.Column(scale=1):
                    ep_dropdown = gr.Dropdown(
                        choices=episode_titles,
                        value=episode_titles[0] if episode_titles else None,
                        label="Select Episode Context"
                    )
                with gr.Column(scale=2):
                    chatbot_kwargs = {"label": "Conversation", "height": 450}
                    if "type" in inspect.signature(gr.Chatbot.__init__).parameters:
                        chatbot_kwargs["type"] = "messages"
                    chatbot = gr.Chatbot(**chatbot_kwargs)
                    with gr.Row():
                        query_input = gr.Textbox(
                            placeholder="Ask a question (e.g., What is OpenRouter's business model?)...",
                            label="Your Question",
                            scale=4
                        )
                        btn_send = gr.Button("Send 🚀", variant="primary", scale=1)

            btn_send.click(
                chat_with_archive,
                inputs=[query_input, ep_dropdown, chatbot],
                outputs=[chatbot, query_input]
            )
            query_input.submit(
                chat_with_archive,
                inputs=[query_input, ep_dropdown, chatbot],
                outputs=[chatbot, query_input]
            )

        # TAB 2: Episode Explorer & Audio Player
        with gr.TabItem("📖 Episode Explorer"):
            explorer_dropdown = gr.Dropdown(
                choices=episode_titles,
                value=episode_titles[0] if episode_titles else None,
                label="Choose an Episode to Read & Listen"
            )
            # Default values are loaded directly on startup
            pub_date_display = gr.Textbox(value=initial_date, label="Published Date", interactive=False)
            audio_display = gr.HTML(value=initial_audio, label="Audio Stream")
            briefing_display = gr.Markdown(value=initial_briefing, label="Executive Briefing")

            explorer_dropdown.change(
                update_episode_view,
                inputs=[explorer_dropdown],
                outputs=[pub_date_display, audio_display, briefing_display]
            )

    btn_sync.click(
        sync_archive,
        inputs=[],
        outputs=[ep_dropdown, explorer_dropdown, archive_status, pub_date_display, audio_display, briefing_display]
    )

if __name__ == "__main__":
    import inspect
    launch_opts = {"server_name": "0.0.0.0", "server_port": 7860}
    if "ssr_mode" in inspect.signature(demo.launch).parameters:
        launch_opts["ssr_mode"] = False
    demo.launch(**launch_opts)

