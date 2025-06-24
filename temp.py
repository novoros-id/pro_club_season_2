from text_to_paragraphs import text_to_paragraphs
file = 'текст.txt'
new_class = text_to_paragraphs(file)
paragraph = new_class.get_text_to_paragraphs()
print(paragraph)