"""
Starting content loaded by `python manage.py load_defaults` (runs on every container start,
only adds what is missing, never overwrites your edits). Change things later in the admin panel.

The matrix below is a PLACEHOLDER inferred from a sample register. Replace it with
the official scoring method (admin panel → Matrix cells) once it is agreed.
"""

# code, English, Greek
LIKELIHOOD = [
    ("A", "Very likely", "Πολύ πιθανό"),
    ("B", "Likely", "Πιθανό"),
    ("C", "Unlikely", "Απίθανο"),
    ("D", "Very unlikely", "Πολύ απίθανο"),
]
CONSEQUENCE = [
    ("1", "Major / fatal", "Σοβαρή / θανατηφόρα"),
    ("2", "Serious", "Σημαντική"),
    ("3", "Moderate", "Μέτρια"),
    ("4", "Minor", "Μικρή"),
]

# code, English, Greek, severity, colour, meaning (EN), meaning (EL)
RATINGS = [
    ("L", "Low", "Χαμηλός", 0, "#2a8749",
     "Acceptable. No further controls needed.",
     "Αποδεκτός. Δεν χρειάζονται επιπλέον μέτρα ελέγχου."),
    ("M", "Moderate", "Μέτριος", 1, "#b67a04",
     "Work may go ahead. Add controls to reduce the risk where practicable.",
     "Η εργασία μπορεί να γίνει. Να ληφθούν επιπλέον μέτρα για εφικτή μείωση του κινδύνου."),
    ("H", "High", "Υψηλός", 2, "#c94c1a",
     "Do not start until the risk is reduced. Act immediately.",
     "Όχι έναρξη εργασιών μέχρι τη μείωση του κινδύνου. Απαιτούνται άμεσα μέτρα."),
    ("E", "Extreme", "Ακραίος", 3, "#9b1a33",
     "Do not start. If the risk cannot be reduced, even with unlimited resources, the work stays prohibited.",
     "Όχι έναρξη εργασιών. Αν ο κίνδυνος δεν μειώνεται ακόμα και με απεριόριστους πόρους, η απαγόρευση συνεχίζεται."),
]

# Rows are likelihood A..D, columns consequence 1..4.
MATRIX = {
    "A": ["E", "E", "H", "H"],
    "B": ["E", "H", "H", "H"],
    "C": ["H", "H", "H", "M"],
    "D": ["H", "M", "M", "L"],
}

# Dropdown lists on the risk task form: (English, Greek)
LISTS = {
    "hazard": [
        ("Slips, trips and falls", "Γλιστρήματα, σκοντάμματα και πτώσεις"),
        ("Unsuitable work environment", "Ακατάλληλο περιβάλλον εργασίας"),
        ("Delayed first aid", "Μη έγκαιρη παροχή πρώτων βοηθειών"),
        ("Manual handling", "Χειρωνακτική διακίνηση φορτίων"),
        ("Low morale and work stress", "Χαμηλό ηθικό και εργασιακό άγχος"),
        ("Forklift and vehicle movement", "Κίνηση περονοφόρων και οχημάτων"),
        ("Electrical equipment", "Ηλεκτρολογικός εξοπλισμός"),
        ("Server room working conditions", "Συνθήκες εργασίας σε αίθουσα διακομιστών"),
        ("Display screen equipment", "Εργασία σε οθόνες"),
        ("Fire", "Πυρκαγιά"),
        ("Working at height", "Εργασία σε ύψος"),
        ("Chemical substances", "Χημικές ουσίες"),
    ],
    "affected": [
        ("Operator", "Χειριστής"),
        ("Other employees", "Άλλοι εργαζόμενοι"),
        ("Third parties", "Τρίτα πρόσωπα"),
        ("Visitors", "Επισκέπτες"),
        ("Contractors", "Εργολάβοι"),
        ("Customers", "Πελάτες"),
    ],
    "consequence": [
        ("Falls and injury", "Πτώση και τραυματισμός"),
        ("Sprains and fractures", "Διαστρέμματα και κατάγματα"),
        ("Head injury", "Τραυματισμός κεφαλής"),
        ("Fatigue and loss of concentration", "Κόπωση και απώλεια συγκέντρωσης"),
        ("Heat stress / heatstroke", "Θερμική καταπόνηση / θερμοπληξία"),
        ("Eye strain", "Καταπόνηση ματιών"),
        ("Hearing damage", "Βλάβη ακοής"),
        ("Back injury and musculoskeletal strain", "Τραυματισμός μέσης και μυοσκελετικές παθήσεις"),
        ("Electric shock and burns", "Ηλεκτροπληξία και εγκαύματα"),
        ("Crush injuries", "Τραυματισμοί σύνθλιψης"),
        ("Stress and low morale", "Άγχος και χαμηλό ηθικό"),
        ("Worsened injury or death", "Επιδείνωση τραυματισμού ή θάνατος"),
    ],
    "control": [
        ("Spills are cleaned up immediately", "Τα υγρά που χύνονται στο πάτωμα μαζεύονται αμέσως"),
        ("Staff wear anti-slip footwear", "Το προσωπικό φοράει αντιολισθητικά παπούτσια"),
        ('"Wet floor" signs used while mopping', "Τοποθετείται πινακίδα «wet floor» κατά το σφουγγάρισμα"),
        ("Floor surfaces are non-slip", "Τα δάπεδα δεν είναι ολισθηρά"),
        ("Walkways kept clear of obstructions", "Οι διάδρομοι διατηρούνται ελεύθεροι από εμπόδια"),
        ("Short, frequent breaks during hot months", "Συχνά και μικρά διαλείμματα τους θερινούς μήνες"),
        ("Cool drinking water always available", "Διαθέσιμο δροσερό πόσιμο νερό"),
        ("Noise measured below legal limits", "Τα επίπεδα θορύβου είναι εντός των επιτρεπτών ορίων"),
        ("Natural and artificial lighting in all areas", "Φυσικός και τεχνητός φωτισμός σε όλους τους χώρους"),
        ("Openings provide fresh-air ventilation", "Ανοίγματα για εισαγωγή νωπού αέρα"),
        ("Indoor temperature kept within comfort range", "Θερμοκρασία εσωτερικών χώρων εντός ορίων άνεσης"),
        ("Measurement records kept on file", "Τα αποτελέσματα των μετρήσεων τηρούνται σε αρχείο"),
        ("First-aid kits in every work area", "Κουτιά πρώτων βοηθειών σε κάθε χώρο εργασίας"),
        ("Emergency numbers displayed", "Αναρτημένα τηλέφωνα έκτακτης ανάγκης"),
        ("Trolleys available for heavy loads", "Διαθέσιμα καροτσάκια για βαριά φορτία"),
        ("Maximum load weights displayed", "Αναρτημένα μέγιστα επιτρεπτά βάρη"),
        ("Equipment inspected periodically", "Περιοδικός έλεγχος εξοπλισμού"),
        ("RCD protection on circuits", "Διακόπτες διαρροής (RCD) στα κυκλώματα"),
        ("Only licensed operators drive forklifts", "Μόνο αδειούχοι χειριστές οδηγούν περονοφόρα"),
        ("Pedestrian walkways marked", "Σημασμένοι διάδρομοι πεζών"),
        ("Access restricted to authorised staff", "Πρόσβαση μόνο σε εξουσιοδοτημένο προσωπικό"),
        ("Cables routed overhead or in trays", "Καλώδια σε σχάρες ή υπερυψωμένα"),
        ("Adjustable chairs provided", "Ρυθμιζόμενες καρέκλες εργασίας"),
        ("Open-door policy with supervisors", "Πολιτική ανοιχτής πόρτας με τους προϊσταμένους"),
        ("Monitors at eye level", "Οθόνες στο ύψος των ματιών"),
        ("Speed limit signs posted", "Αναρτημένες πινακίδες ορίου ταχύτητας"),
        ("Lone-working check-in procedure", "Διαδικασία ελέγχου για μοναχική εργασία"),
    ],
    "measure": [
        ("Check the route for wet or obstructed areas before moving materials",
         "Έλεγχος της διαδρομής για ολισθηρές επιφάνειες ή εμπόδια πριν τη μεταφορά υλικών"),
        ("Mark changes in floor level with contrasting tape", "Σήμανση αλλαγών στάθμης δαπέδου με ταινία αντίθεσης"),
        ("Install thermometers and hygrometers in storage areas",
         "Τοποθέτηση θερμομέτρων και υγρασιομέτρων στους χώρους αποθήκευσης"),
        ("Rotate tasks and schedule deliveries in the morning during heatwaves",
         "Εναλλαγή δραστηριοτήτων και παραλαβές τις πρωινές ώρες σε συνθήκες καύσωνα"),
        ("Train staff in first aid and keep certificates current",
         "Εκπαίδευση προσωπικού στις πρώτες βοήθειες και ανανέωση πιστοποιητικών"),
        ("Check first-aid kit contents against legal requirements and restock",
         "Έλεγχος περιεχομένου κουτιών πρώτων βοηθειών βάσει νομοθεσίας και αναπλήρωση"),
        ("Deliver manual handling training to all staff",
         "Εκπαίδευση όλου του προσωπικού στη χειρωνακτική διακίνηση φορτίων"),
        ("Move heavy items to waist-height storage", "Αποθήκευση βαριών αντικειμένων στο ύψος της μέσης"),
        ("Run an anonymous staff wellbeing survey", "Ανώνυμη έρευνα ευημερίας προσωπικού"),
        ("Test and label portable electrical equipment", "Έλεγχος και σήμανση φορητού ηλεκτρολογικού εξοπλισμού"),
        ("Replace damaged extension leads", "Αντικατάσταση φθαρμένων προεκτάσεων ρεύματος"),
        ("Fit convex mirrors at blind corners", "Τοποθέτηση κυρτών καθρεπτών στις τυφλές γωνίες"),
        ("Provide hearing protection at the server room entrance",
         "Ωτοασπίδες διαθέσιμες στην είσοδο της αίθουσας διακομιστών"),
        ("Install floor-tile lifters and mark open tiles",
         "Εργαλεία ανύψωσης πλακιδίων και σήμανση ανοιχτών πλακιδίων"),
        ("Complete a workstation assessment for each employee", "Αξιολόγηση θέσης εργασίας για κάθε εργαζόμενο"),
        ("Provide footrests and laptop stands on request", "Υποπόδια και βάσεις φορητών υπολογιστών κατόπιν αιτήματος"),
        ("Install barriers between walkways and racking aisles", "Τοποθέτηση προστατευτικών μεταξύ διαδρόμων πεζών και ραφιών"),
        ("Agree a fixed break schedule with each team", "Συμφωνία σταθερού προγράμματος διαλειμμάτων με κάθε ομάδα"),
        ("Add a heated rest area outside the cold aisle", "Θερμαινόμενος χώρος ανάπαυσης έξω από τον ψυχρό διάδρομο"),
    ],
}
