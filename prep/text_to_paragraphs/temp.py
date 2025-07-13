from text_to_paragraphs import text_to_paragraphs
full_text = 'На улице ветренно. Собака пошла гулять.'

class_text_to_paragraphs = text_to_paragraphs(full_text)
paragraphs = class_text_to_paragraphs.get_text_to_paragraphs()
print (paragraphs)