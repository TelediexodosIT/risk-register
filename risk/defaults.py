"""
Starting content loaded by `python manage.py load_defaults`.
Edit freely, or change things later in the admin panel.

The matrix below is a PLACEHOLDER inferred from a sample register. Replace it with
the official scoring method (admin panel → Matrix cells) once it is agreed.
"""

LIKELIHOOD = [("A", "Very likely"), ("B", "Likely"), ("C", "Unlikely"), ("D", "Very unlikely")]
CONSEQUENCE = [("1", "Major / fatal"), ("2", "Serious"), ("3", "Moderate"), ("4", "Minor")]

# code, label, severity, colour, what it means
RATINGS = [
    ("L", "Low", 0, "#2a8749", "Acceptable. No further controls needed."),
    ("M", "Moderate", 1, "#b67a04", "Work may go ahead. Add controls to reduce the risk where practicable."),
    ("H", "High", 2, "#c94c1a", "Do not start until the risk is reduced. Act immediately."),
    ("E", "Extreme", 3, "#9b1a33", "Do not start. If the risk cannot be reduced, even with unlimited resources, the work stays prohibited."),
]

# Rows are likelihood A..D, columns consequence 1..4.
MATRIX = {
    "A": ["E", "E", "H", "H"],
    "B": ["E", "H", "H", "H"],
    "C": ["H", "H", "H", "M"],
    "D": ["H", "M", "M", "L"],
}

# name, category, consequences, [existing controls], [additional measures]
LIBRARY = [
    ("Slips, trips and falls", "Floors and access", "Falls causing sprains, fractures or head injury",
     ["Spills are cleaned up immediately", "Staff wear anti-slip footwear", '"Wet floor" signs used while mopping',
      "Floor surfaces are non-slip", "Walkways kept clear of obstructions"],
     ["Check the route for wet or obstructed areas before moving materials", "Mark changes in floor level with contrasting tape"]),
    ("Unsuitable work environment", "Heat, humidity, lighting, ventilation, noise",
     "Fatigue, loss of concentration, heat stress, eye strain, hearing damage",
     ["Short, frequent breaks during hot months", "Cool drinking water always available", "Noise measured below legal limits",
      "Natural and artificial lighting in all areas", "Openings provide fresh-air ventilation",
      "Indoor temperature kept within comfort range", "Measurement records kept on file"],
     ["Install thermometers and hygrometers in storage areas", "Rotate tasks and schedule deliveries in the morning during heatwaves"]),
    ("Delayed first aid", "Emergency response",
     "Injury worsened or fatal because no trained person or kit is available; staff stress and low morale",
     ["First-aid kits in every work area", "Emergency numbers displayed"],
     ["Train staff in first aid and keep certificates current", "Check first-aid kit contents against legal requirements and restock"]),
    ("Manual handling", "Ergonomics", "Back injury and musculoskeletal strain",
     ["Trolleys available for heavy loads", "Maximum load weights displayed"],
     ["Deliver manual handling training to all staff", "Move heavy items to waist-height storage"]),
    ("Low morale and work stress", "Psychosocial", "Lower performance, absence, mistakes",
     ["Open-door policy with supervisors"],
     ["Run an anonymous staff wellbeing survey", "Agree a fixed break schedule with each team"]),
    ("Forklift and vehicle movement", "Workplace transport", "Crush injuries and collisions with pedestrians",
     ["Only licensed operators drive forklifts", "Pedestrian walkways marked", "Speed limit signs posted"],
     ["Fit convex mirrors at blind corners", "Install barriers between walkways and racking aisles"]),
    ("Electrical equipment", "Equipment", "Electric shock, burns, fire",
     ["Equipment inspected periodically", "RCD protection on circuits"],
     ["Test and label portable electrical equipment", "Replace damaged extension leads"]),
    ("Server room working conditions", "Noise, airflow, cabling", "Hearing fatigue, cold stress, trips over floor cabling",
     ["Access restricted to authorised staff", "Cables routed overhead or in trays", "Lone-working check-in procedure"],
     ["Provide hearing protection at the server room entrance", "Install floor-tile lifters and mark open tiles",
      "Add a heated rest area outside the cold aisle"]),
    ("Display screen equipment", "Ergonomics", "Neck, back and wrist strain; eye strain",
     ["Adjustable chairs provided", "Monitors at eye level"],
     ["Complete a workstation assessment for each employee", "Provide footrests and laptop stands on request"]),
]
