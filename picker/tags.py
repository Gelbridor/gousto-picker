"""Derive 'main protein' and 'cuisine' tags from recipe names (the feed has neither)."""

PROTEINS = [  # first match wins, so more specific words come first
    ("Seafood", ["prawn", "shrimp", "scallop", "mussel", "squid", "crab"]),
    ("Fish", ["salmon", "basa", "cod", "sea bass", "haddock", "tuna", "fish", "trout", "mackerel", "cullen skink", "pollock", "fishcake"]),
    ("Chicken", ["chicken"]),
    ("Beef", ["beef", "steak", "brisket", "burger", "meatball"]),
    ("Pork", ["pork", "sausage", "bacon", "chorizo", "gammon", "ham ", "pancetta", "nduja", "carbonara", "prosciutto", "amatriciana"]),
    ("Lamb", ["lamb"]),
    ("Duck & game", ["duck", "venison"]),
    ("Turkey", ["turkey"]),
    ("Veggie", ["tofu", "halloumi", "paneer", "chickpea", "lentil", "falafel", "veg", "mushroom", "cauliflower",
                      "aubergine", "bean", "ricotta", "cheese", "gnocchi", "risotto", "squash", "meat-free", "plant"]),
]

CUISINES = [
    ("Indian", ["curry", "tikka", "korma", "masala", "dal", "biryani", "tandoori", "paneer", "madras", "balti", "bhuna", "jalfrezi", "rogan", "saag", "keema", "naan", "chaat", "indian", "dhansak"]),
    ("Thai & SE Asian", ["thai", "laksa", "satay", "pad ", "massaman", "nasi", "rendang", "bao", "vietnam", "banh", "lemongrass", "coconut"]),
    ("Chinese & East Asian", ["teriyaki", "chow mein", "noodle", "katsu", "ramen", "miso", "stir", "fried rice", "sesame", "hoisin", "kung pao", "szechuan", "sichuan", "gyoza", "korean", "bulgogi", "gochujang", "japanese", "bibimbap", "sweet & sour", "chinese", "sweet 'n'", "sweet chilli", "teppanyaki", "sushi", "poke", "dumpling", "udon"]),
    ("Mexican & Latin", ["taco", "burrito", "fajita", "chipotle", "quesadilla", "enchilada", "nacho", "mexican", "cajun", "jerk", "chimichurri", "salsa", "tex-mex", "chilli con", "peruvian", "brazil"]),
    ("Italian", ["pasta", "spaghetti", "bolognese", "gnocchi", "risotto", "carbonara", "ravioli", "tagliatelle", "tortiglioni", "orzo", "lasagne", "penne", "pesto", "pizza", "parmigiana", "ragu", "ragù", "italian", "cacio", "linguine", "rigatoni", "fusilli", "arrabbiata", "puttanesca", "pappardelle", "tortellini", "calzone", "orecchiette"]),
    ("Middle Eastern & Med", ["shawarma", "falafel", "harissa", "greek", "tzatziki", "couscous", "moroccan", "tagine", "kebab", "souvlaki", "gyro", "shakshuka", "za'atar", "zaatar", "persian", "turkish", "lebanese", "mezze", "hummus", "pitta", "spanish", "paella", "dukkah", "ras el"]),
    ("American & Diner", ["burger", "hot dog", "mac ", "mac &", "bbq", "barbecue", "buffalo", "wings", "pulled", "philly", "cheesesteak", "slider", "ranch", "loaded", "diner", "fried chicken", "nugget", "popcorn", "southern", "cheeseburger"]),
    ("British & Comfort", ["pie", "roast", "cottage", "shepherd", "mash", "bangers", "fish & chips", "fish and chips", "hotpot", "stew", "pot roast", "cauliflower cheese", "gammon", "yorkshire", "gastropub", "coq au vin", "cullen skink", "toad", "crumble", "colcannon", "chowder", "parmo", "battered", "chips", "meuni", "pasties", "wellington", "sausage"]),
]


def _match(rules, text, default):
    for label, words in rules:
        if any(w in text for w in words):
            return label
    return default


def tag(name):
    t = " " + name.lower() + " "
    return _match(PROTEINS, t, "Other"), _match(CUISINES, t, "Other")
