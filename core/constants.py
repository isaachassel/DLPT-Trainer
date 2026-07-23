from __future__ import annotations

ILR_LEVELS = ["0", "0+", "1", "1+", "2", "2+", "3"]
ILR_THETA = {
    "0": -2.50,
    "0+": -1.75,
    "1": -1.00,
    "1+": -0.25,
    "2": 0.50,
    "2+": 1.25,
    "3": 2.00,
}
THETA_ILR = tuple((theta, level) for level, theta in ILR_THETA.items())
SKILLS = ["reading", "listening"]
MODES = ["training", "diagnostic", "simulation"]
QUESTION_TYPES = [
    "main idea",
    "prominent detail",
    "inference",
    "speaker/writer intent",
    "tone or attitude",
    "reference",
    "sequence",
    "cause and effect",
    "relationship of ideas",
    "meaning from context",
]
PASSAGE_STATUS = ["active", "quarantined", "retired"]
SOURCE_TYPES = ["authentic/open-licensed", "transformed/adapted", "synthetic"]
VALIDATION_STATUSES = ["accepted", "rejected", "needs_review"]
LETTERS = ["A", "B", "C", "D"]

MODE_LABELS = {
    "Training Mode": "training",
    "Adaptive Diagnostic": "diagnostic",
    "Full CA Simulation": "simulation",
}
SKILL_LABELS = {
    "Reading": ["reading"],
    "Listening": ["listening"],
    "Reading + Listening (separate sections)": ["reading", "listening"],
}

TRAINING_LENGTHS = {
    "Short — 8 questions": 8,
    "Standard — 16 questions": 16,
    "Long — 24 questions": 24,
}
DIAGNOSTIC_LENGTHS = {
    "Efficient — 12 to 20 questions per skill": 20,
    "Extended — 16 to 28 questions per skill": 28,
}
SIMULATION_LENGTHS = {
    "Shortened — 12 questions per skill (not a full simulation)": 12,
    "Standard — 35 questions per skill": 35,
    "Full-length — minimum 35, up to 60 questions / 3 hours per skill": 60,
}
SIMULATION_MIN_QUESTIONS = 35
MAX_READING_QUESTIONS_PER_PASSAGE = 5
MAX_LISTENING_QUESTIONS_PER_PASSAGE = 3
DISCLAIMER = (
    "Independent practice product. Not official DLPT material. Not affiliated with DLIFLC, DoD, "
    "or any government testing authority. No official score is generated; estimates are for practice guidance only."
)
