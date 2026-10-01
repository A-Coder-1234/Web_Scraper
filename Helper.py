# Contains complex logic in an atempt to clean up space in the other scripts.

### Sort by relevance logic
# Defines variables used for debugging. Later defined in other scripts.
items = [
    "https://www.woolworths.co.nz/shop/product-details/286361/Name-Thing-Chips",
    "https://www.woolworths.co.nz/shop/product-details/286362/Other-Name-Thing-Chips",
    "https://www.woolworths.co.nz/shop/product-details/286363/Name-thing-corn",
    "https://www.woolworths.co.nz/shop/product-details/286364/Name-thing-corn-chips",
    "https://www.woolworths.co.nz/shop/product-details/286365/Corny-Chips"
         ]
keywords = ["name", "chips"]
output = []
def sort_items(items, keywords, output):
    # defines key variables used for storing the scores.)
    scores = []

    # Loops through each item in the list of items to be sorted.
    for item in items:
        
        # Defines key variables.
        words_in_name = []

        # Slices, lowers and splits the item name into a list of words.
        words_in_name = item.split("/")[-1].lower().split("-")

        # Scores the item based on how many of the total words in the item name match keywords. This will output a percentage for each item.
        scores.append(0)
        for word in words_in_name:
            if word in keywords:
                scores[-1] = scores[-1] + 1
        scores[-1] = f"{round(scores[-1] / len(words_in_name) * 100, 2)},{item}"

    # Sorts the scores in descending order.
    scores.sort(key=lambda x: float(x.split(',')[0]), reverse=True)

    # remove the score from the output, leaving only the item name.
    output = [x.split(',')[1] for x in scores]

sort_items(items, keywords, output)
print(output)