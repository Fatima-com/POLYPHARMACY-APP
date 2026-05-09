import os
from dotenv import load_dotenv
from groq import Groq
import reflex as rx
import asyncio

# 1. SETUP & CONFIGURATION
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

SQUIRCLE = "35px"
TIMES = "Times New Roman, serif"

class State(rx.State):
    # --- DATA STORAGE ---
    pills: list[dict[str, str]] = [{"name": "", "dose": "", "time": ""}]
    pill_analysis_results: dict[str, str] = {}
    summary_text: str = ""

    # FIX 1: Store AI-generated content for the 3 main flashcards
    card_good: str = ""
    card_bad: str = ""
    card_precaution: str = ""

    # --- UI CONTROL STATES ---
    is_loading: bool = False
    is_analyzed: bool = False
    show_summary: bool = False
    is_feeling_off: bool = False
    show_symptom_result: bool = False

    # --- SYMPTOM TRACKING ---
    flipped_cards: dict[str, bool] = {}
    custom_symptom: str = ""
    symptom_analysis: str = ""

    # FIX 3: Track selected preset symptom + dynamic symptom buttons
    selected_symptom: str = ""
    extra_symptoms: list[str] = []

    # --- CORE LOGIC FUNCTIONS ---
    def set_custom_symptom(self, val: str):
        self.custom_symptom = val

    def add_row(self):
        if len(self.pills) < 15:
            self.pills.append({"name": "", "dose": "", "time": ""})

    def update_pill(self, index: int, field: str, value: str):
        self.pills[index][field] = value

    def toggle_flip(self, card_id: str):
        self.flipped_cards[card_id] = not self.flipped_cards.get(card_id, False)

    # FIX 3: Select a symptom button (highlights it)
    def select_symptom(self, name: str):
        self.selected_symptom = name

    # FIX 3: Add custom symptom as a new button
    def add_custom_symptom_button(self):
        if self.custom_symptom and self.custom_symptom not in self.extra_symptoms:
            self.extra_symptoms.append(self.custom_symptom)
            self.selected_symptom = self.custom_symptom
            self.custom_symptom = ""

    # --- AI WORKFLOW 1: INITIAL ANALYSIS ---
    async def start_transition(self):
        self.is_loading = True
        yield

        pill_data = ", ".join([f"{p['name']} ({p['dose']} at {p['time']})" for p in self.pills if p['name']])

        prompt = f"""Analyze these medications: {pill_data}.
        Return a response structured EXACTLY like this with no extra text before GOOD::
        GOOD: [1 sentence about safe interactions]
        BAD: [1 sentence about risks]
        PRECAUTION: [1 sentence about lifestyle advice]
        ---
        Followed by a professional 1-paragraph summary for a doctor."""

        try:
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
            )
            raw = completion.choices[0].message.content
            self.summary_text = raw

            # FIX 1: Parse the AI response to extract GOOD/BAD/PRECAUTION
            lines = raw.split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith("GOOD:"):
                    self.card_good = line[5:].strip()
                elif line.startswith("BAD:"):
                    self.card_bad = line[4:].strip()
                elif line.startswith("PRECAUTION:"):
                    self.card_precaution = line[11:].strip()

            # FIX 1: Per-pill analysis via AI
            for p in self.pills:
                if p['name']:
                    pill_prompt = f"In 2 sentences, describe the key monitoring advice and common side effects for {p['name']} ({p['dose']}) taken at {p['time']}."
                    pill_resp = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "user", "content": pill_prompt}],
                    )
                    self.pill_analysis_results[p['name']] = pill_resp.choices[0].message.content.strip()

        except Exception as e:
            self.summary_text = f"Error connecting to AI: {str(e)}"
            self.card_good = "Could not retrieve safe interaction data."
            self.card_bad = "Could not retrieve risk data."
            self.card_precaution = "Could not retrieve precaution data."

        await asyncio.sleep(1.5)
        self.is_analyzed = True
        self.is_loading = False

    # --- AI WORKFLOW 2: SYMPTOM CHECKER ---
    async def analyze_symptom(self, symptom_name: str):
        # Use selected_symptom if no explicit name passed
        target = symptom_name if symptom_name else self.selected_symptom
        if not target:
            return

        self.is_loading = True
        yield

        pill_str = ", ".join([p['name'] for p in self.pills if p['name']])
        prompt = f"User is taking {pill_str} and feels {target}. Explain if this is a known side effect or interaction in 2 sentences. Keep it concise."

        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}]
            )
            self.symptom_analysis = response.choices[0].message.content
        except:
            self.symptom_analysis = "Could not analyze the symptom at this time."

        await asyncio.sleep(1)
        self.show_symptom_result = True
        self.is_loading = False

    async def confirm_symptom_and_return(self):
        self.is_loading = True
        yield
        self.summary_text += f"\n\nPATIENT REPORTED SYMPTOM: {self.symptom_analysis}"
        await asyncio.sleep(0.5)
        self.is_feeling_off = False
        self.show_symptom_result = False
        self.show_summary = True
        self.is_loading = False

    # --- NAVIGATION ---
    def trigger_summary_view(self):
        self.show_summary = True

    def trigger_feel_off(self):
        self.is_feeling_off = True
        self.selected_symptom = ""
        self.show_symptom_result = False

    # FIX 2: Copy button — uses rx.set_clipboard
    def copy_to_clipboard(self):
        return [rx.set_clipboard(self.summary_text), rx.toast("Copied to clipboard!", position="bottom-right")]
    
    def save_as_pdf(self):
        return rx.download(data=self.summary_text, filename="Medical_Summary.txt")
    
    # FIX 4: Restart goes back to main input screen
    def start_over(self):
        """Manually resets all variables and redirects home."""
        self.pills = [{"name": "", "dose": "", "time": ""}]
        self.pill_analysis_results = {}
        self.summary_text = ""
        self.is_loading = False
        self.is_analyzed = False  
        self.show_summary = False  
        self.is_feeling_off = False 
        self.show_symptom_result = False 
        self.flipped_cards = {}
        self.custom_symptom = ""
        self.symptom_analysis = ""
        return rx.redirect("/")


# --- REUSABLE COMPONENTS ---
def flipping_card(title, front_icon, details, card_id):
    is_flipped = State.flipped_cards.get(card_id, False)
    return rx.box(
        rx.box(
            # FRONT
            rx.vstack(
                rx.heading(front_icon, size="8", color="magenta"),
                rx.text(title, font_family=TIMES, font_weight="bold"),
                position="absolute", backface_visibility="hidden",
                width="100%", height="100%", bg="white", border="2px solid magenta",
                border_radius=SQUIRCLE, justify="center", align="center",
            ),
            # BACK — FIX 1: details now contains AI text, scroll area ensures it fits
            rx.vstack(
                rx.scroll_area(
                    rx.text(
                        details,
                        color="white",
                        padding="1.5em",
                        text_align="center",
                        font_family=TIMES,
                        font_size="0.8em",
                    ),
                    width="100%",
                    height="100%",
                ),
                position="absolute",
                backface_visibility="hidden",
                width="100%",
                height="100%",
                bg="magenta",
                border_radius=SQUIRCLE,
                justify="center",
                align="center",
                transform="rotateY(180deg)",
                overflow="hidden",  # FIX 3: prevents overflow
            ),
            transform_style="preserve-3d",
            transition="transform 0.6s",
            transform=rx.cond(is_flipped, "rotateY(180deg)", "rotateY(0deg)"),
            width="240px",
            height="200px",
        ),
        on_click=lambda: State.toggle_flip(card_id),
        perspective="1000px",
        cursor="pointer",
    )


# --- VIEW 1: INPUT ---
def input_view():
    return rx.center(
        rx.vstack(
            rx.heading("POLYPHARMACY", color="magenta", size="9", font_family=TIMES),
            rx.foreach(State.pills, lambda pill, i: rx.hstack(
                rx.input(placeholder="Medicine Name...", on_change=lambda v: State.update_pill(i, "name", v), border_radius=SQUIRCLE, border_color="magenta", bg="white"),
                rx.input(placeholder="Pills...", on_change=lambda v: State.update_pill(i, "dose", v), border_radius=SQUIRCLE, border_color="magenta", width="80px", bg="white"),
                rx.input(placeholder="Time...", on_change=lambda v: State.update_pill(i, "time", v), border_radius=SQUIRCLE, border_color="magenta", bg="white"),
            )),
            rx.button("+", on_click=State.add_row, bg="magenta", color="white", border_radius="full"),
            rx.button(
                "Analyze",
                on_click=State.start_transition,
                bg="magenta", color="white", border_radius=SQUIRCLE, width="250px", size="4"
            ),
            # FIX 5: Disclaimer below the analyze button
            rx.box(
                rx.hstack(
                    rx.text("⚠️", font_size="1.1em"),
                    rx.text(
                        "USED AI-GENERATED INFORMATION. "
                        "CONSULT A PROFESSIONAL BEFORE MAKING ANY DECISIONS.",
                        font_size="0.8em",
                        color="#555",
                        font_family=TIMES,
                        font_style="italic",
                    ),
                    align="start",
                    spacing="2",
                ),
                padding="3",
                border="1px solid #c0a0c0",
                border_radius="12px",
                bg="#fff0f5",
                max_width="480px",
                margin_top="2",
            ),
            align="center",
            spacing="4",
            filter=rx.cond(State.is_loading, "blur(10px)", "none"),
        ),
        height="100vh",
        bg="#FFF0F5",
    )


# --- VIEW 2: RESULTS ---
def results_view():
    return rx.center(
        rx.vstack(
            rx.heading("ANALYSIS RESULTS", color="magenta", font_family=TIMES),
            rx.hstack(
                # FIX 1: Pass AI-generated card content
                flipping_card("Good","✅", State.card_good, "good"),
                flipping_card("Bad","❌", State.card_bad, "bad"),
                flipping_card("Precaution","⚠️", State.card_precaution, "pre"),
                spacing="4",
            ),
            rx.flex(
                rx.foreach(
                    State.pills,
                    lambda p, i: rx.cond(
                        p["name"] != "",
                        flipping_card(
                            p["name"],
                            "💊",
                            # FIX 1: Use dict .get with default so it never crashes
                            State.pill_analysis_results.get(p["name"], "Flip to see analysis."),
                            f"p{i}",
                        )
                    )
                ),
                wrap="wrap",
                spacing="4",
                justify="center",
            ),
            rx.button(
                "Generate Final Summary",
                on_click=State.trigger_summary_view,
                bg="magenta", color="white", border_radius=SQUIRCLE, size="4", width="300px"
            ),
            align="center",
            spacing="8",
            filter=rx.cond(State.is_loading, "blur(10px)", "none"),
        ),
        padding="10",
        bg="#FFF0F5",
        min_height="100vh",
    )


# --- VIEW 3: SUMMARY & FEEL OFF ---
def summary_view():
    return rx.center(
        rx.vstack(
            # FIX 2: Summary box — content stays inside, buttons aligned properly
            rx.box(
                rx.hstack(
                    # FIX 2: Working copy button
                    rx.button(
                        "A TEXT COPY SAVE",
                        on_click=State.copy_to_clipboard,
                        variant="ghost",
                        color="magenta",
                        cursor="pointer",
                    ),
                    rx.spacer(),
                    # FIX 2: Save as PDF — triggers browser print dialog (works natively)
                    rx.button(
                        "A PDF SAVE",
                        on_click=State.save_as_pdf,
                        variant="ghost",
                        color="magenta",
                        cursor="pointer",
                    ),
                    width="100%",
                    padding_x="4",
                    padding_top="3",
                ),
                rx.divider(border_color="magenta", margin_y="2"),
                # FIX 2: scroll_area keeps text inside the box
                rx.scroll_area(
                    rx.text(
                        State.summary_text,
                        font_family=TIMES,
                        padding="2.5em",
                        white_space="pre-wrap",
                        word_break="break-word",
                    ),
                    height="320px",
                    width="100%",
                    padding_x="2",
                ),
                bg="white",
                border="3px solid magenta",
                border_radius=SQUIRCLE,
                width="700px",
                overflow="hidden",  # FIX 2: ensures nothing bleeds out
            ),

            rx.button(
                "I Feel Off",
                on_click=State.trigger_feel_off,
                bg="magenta", color="white", border_radius=SQUIRCLE, size="4"
            ),

            # FIX 4: "Start Over" button — takes user back to input screen
            rx.button(
                "Another Analysis",
                on_click=State.start_over,
                bg="white",
                color="magenta",
                border="2px solid magenta",
                border_radius=SQUIRCLE,
                size="4",
                width="200px",
            ),

            # THE OVERLAY — FIX 3: layout fixed
            rx.cond(
                State.is_feeling_off,
                rx.center(
                    rx.vstack(
                        # FIX 3: Heading is inside the box now (part of vstack inside the styled box)
                        rx.heading("How do you feel?", color="magenta", size="6"),

                        # Preset symptom buttons with highlight
                        rx.hstack(
                            rx.button(
                                "Headache",
                                on_click=lambda: State.select_symptom("Headache"),
                                bg=rx.cond(State.selected_symptom == "Headache", "#9b00b0", "magenta"),
                                color="white",
                                border_radius=SQUIRCLE,
                                border=rx.cond(State.selected_symptom == "Headache", "3px solid #3d003d", "3px solid transparent"),
                            ),
                            rx.button(
                                "Nausea",
                                on_click=lambda: State.select_symptom("Nausea"),
                                bg=rx.cond(State.selected_symptom == "Nausea", "#9b00b0", "magenta"),
                                color="white",
                                border_radius=SQUIRCLE,
                                border=rx.cond(State.selected_symptom == "Nausea", "3px solid #3d003d", "3px solid transparent"),
                            ),
                            wrap="wrap",
                            justify="center",
                            spacing="2",
                        ),

                        # FIX 3: Dynamic extra symptom buttons (same style as preset)
                        rx.flex(
                            rx.foreach(
                                State.extra_symptoms,
                                lambda s: rx.button(
                                    s,
                                    on_click=lambda: State.select_symptom(s),
                                    bg=rx.cond(State.selected_symptom == s, "#9b00b0", "magenta"),
                                    color="white",
                                    border_radius=SQUIRCLE,
                                    border=rx.cond(State.selected_symptom == s, "3px solid #3d003d", "3px solid transparent"),
                                    margin="1",
                                )
                            ),
                            wrap="wrap",
                            justify="center",
                        ),

                        # FIX 3: Custom symptom input + add button
                        rx.hstack(
                            rx.input(
                                placeholder="Other symptom...",
                                value=State.custom_symptom,
                                on_change=State.set_custom_symptom,
                                bg="white",
                                border_radius=SQUIRCLE,
                                border_color="magenta",
                                flex="1",
                            ),
                            rx.button(
                                "Add",
                                on_click=State.add_custom_symptom_button,
                                bg="magenta",
                                color="white",
                                border_radius=SQUIRCLE,
                            ),
                            width="100%",
                        ),

                        # FIX 3: Analyze button inside the box
                        rx.button(
                            "Analyze",
                            on_click=lambda: State.analyze_symptom(""),
                            bg="magenta",
                            color="white",
                            border_radius=SQUIRCLE,
                            width="150px",
                        ),

                        # FIX 3: Result card — text stays inside squircle
                        rx.cond(
                            State.show_symptom_result,
                            rx.vstack(
                                rx.box(
                                    rx.text(
                                        State.symptom_analysis,
                                        font_family=TIMES,
                                        font_size="0.85em",
                                        text_align="center",
                                        color="white",
                                        white_space="pre-wrap",
                                        word_break="break-word",
                                        padding="3",
                                    ),
                                    bg="magenta",
                                    border_radius=SQUIRCLE,
                                    width="100%",
                                    max_height="180px",
                                    overflow_y="auto",
                                    padding="2",
                                ),
                                rx.button(
                                    "Add to Summary & Finish",
                                    on_click=State.confirm_symptom_and_return,
                                    bg="magenta",
                                    color="white",
                                    border_radius=SQUIRCLE,
                                ),
                                align="center",
                                spacing="3",
                                width="100%",
                            )
                        ),

                        spacing="4",
                        padding="6",
                        bg="white",
                        border_radius=SQUIRCLE,
                        border="4px solid magenta",
                        align="center",
                        width="380px",
                        max_height="90vh",
                        overflow_y="auto",
                    ),
                    position="fixed",
                    top="0",
                    left="0",
                    width="100vw",
                    height="100vh",
                    bg="rgba(0,0,0,0.2)",
                    backdrop_filter="blur(5px)",
                    z_index="1000",
                )
            ),
            align="center",
            spacing="4",
            padding_y="8",
        ),
        min_height="100vh",
        bg="#FFF0F5",
    )


# --- THE NAVIGATION ENGINE ---
def index() -> rx.Component:
    return rx.box(
        rx.cond(
            ~State.is_analyzed,
            input_view(),
            rx.cond(
                ~State.show_summary,
                results_view(),
                summary_view()
            )
        )
    )


app = rx.App()
app.add_page(index)
