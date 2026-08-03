# Before running the program, we must make sure the vitual environment is correct
# Steps to do so:
    # In VS code, Python: Select Interpreter
    # Select the interpreter containing: env\Scripts\python.exe
    
    


import os

# import python regex library
import re
# import pretty print library
from pprint import pprint
# use natual language tool kit library
import nltk
# 'punkt' and 'punkt_tab' are tokenizer data files used by sent_tokenize.
nltk.download('punkt', quiet = True)
nltk.download('punkt_tab', quiet = True)
# importing sentence tokenizer
from nltk.tokenize import sent_tokenize
# this allows us to return a list of sentences from 1 string line


import time
import csv
from pathlib import Path
from dotenv import load_dotenv
# import Gemini AI 
from google import genai
from google.genai import types

# Get the folder where this Python file is located
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

api_key=os.getenv("GEMINI_API_KEY")

print("Current working directory:", os.getcwd())
print("Python file directory:", BASE_DIR)
print("API key loaded:", api_key is not None)
print("API key preview:", api_key[:8] if api_key else "None")

#client is an object that lets your Python code talk to Gemini
# kinda like scanner in java
"""
client = genai.Client(api_key=api_key)
response  = client.models.generate_content_stream(
    model='gemini-2.5-flash',
    contents=types.Part.from_text(text='Why is the sky blue?'),
    config=types.GenerateContentConfig(
        # temperature controls the randomness, lower temperature means more predictable, higher temperature means more creative
        temperature=0.2,
        # top_p controls the number of words the model considers when generating
        top_p=0.95,
        # top_k consider how many next tokens/words the model considers
        top_k=20,
    )
)

# output the response line by line
for stream in response:
    print(stream.text)
"""
class FlashCardApp():
    def __init__(self):
        self.lines=[]
        self.tokenised=[]
        self.flash_cards=[]
        self.seperaterList = ("-","|",":",";",",","  ","_","\n")
        self.QUESTION_STARTERS = ('what', 'who', 'where', 'when', 'why', 'how', 
            'which', 'define', 'explain', 'describe', 'list'
        )
        
        self.DEFINITION_PATTERNS = [
            # word based definition patterns 
            r'(.+?) is (?:a|an|the) (.+)',
            r'(.+?) refers to (.+)',
            r'(.+?) is defined as (.+)',
            r'(.+?) means (.+)',
            r'(.+?), (?:which|who) is (.+)',
            
            # symbol based definition patterns
             r'(.+?)\s*:\s*(.+)',
        ]

        
        raw_text = "\n".join(self.user_input_list())
        cleaned_text = self.clean_text(raw_text)
        print(cleaned_text)
        self.flash_cards = self.extract_flashcards(cleaned_text)
        
        self.display_list(self.flash_cards)        
    
        
    
        
    def user_input_list(self) -> list[str]:
        list=[]        
        print("Please paste your notes here:")
        print("Type 'END' to finish input.")
        while True:
            line = input()
            if line=="END":
                break
            list.append(line)
        return list
    
        
            
    def display_list(self, arr):
        print("display_list ran")
        for block in arr:
            print(block)
        print("successfully printed")    
            
    def clean_text(self, text: str) -> str:
        # Convert all line-ending styles to \n.
        text = text.replace('\r\n', '\n').replace('\r', '\n')

        # Keep one \n between lines; remove blank lines.
        text = re.sub(r'\n+', '\n', text)

        # Remove spaces before punctuation.
        text = re.sub(r'\s+([?.!,])', r'\1', text)

        # Collapse repeated spaces and tabs without removing \n.
        text = re.sub(r'[^\S\n]+', ' ', text)

        return text.strip()
    
    # add before split_sentence
    def colon_pattern(self, text: str)  -> list[dict]:
        """To identify cloze card, check for label-definition pairs
        
        Args:
            text: bulk notes imported from user
            
        Returns:
            a list of dictionary 
        """

        #Splits when there is a new line
        lines=text.split('\n')
        blocks=[]
        i = 0
        
        while i < len(lines):
            line=lines[i].strip()
            
            # skip if line is empty
            if not line:
                i += 1
                continue
            
            """
            Use regex to identify a label followed by a colon and optional content.
            Pattern: ^([A-Z][^:]{1,40}):\s*(.*)
            
            '^' means the match must start at the beginning of the line.
            
            Pattern #1: ([A-Z][^:]{1,40})
            This captures the label.
            '[A-Z]' means the label must start with a capital letter.
            '[^:]' means any character except a colon.
            '{1,40}' allows 1 to 40 additional non-colon characters.
            The label must therefore contain 2 to 41 characters total.
            For example, 'A:' will not match, but 'AI:' will match.
            
            ':' requires a colon immediately after the label.
            
            '\s*' means zero or more whitespace characters after the colon.
            This allows both 'Term:definition' and 'Term: definition'.
            
            Pattern #2: (.*)
            This captures all remaining text after the colon as inline content.
            The content may be empty, so 'Term:' still matches.
            """
            # Implement AI to replace the code algorithm
            LABEL_PATTERN = re.compile(
                r"^(?P<label>[A-Z][^:\n]{1,40}?)\s*:\s*(?P<content>.*)$"
            )
            
            # Label/definition patterns on the same line
            label_match = LABEL_PATTERN.match(line)
            label = label_match["label"].strip()
            inline_content = label_match["content"].strip()
            
            if label_match:
                label = label_match.group(1).strip()
                inline_content = label_match.group(2).strip()
                
                # check later lines for content to match with label
                content_lines=[]
                if inline_content:
                    content_lines.append(inline_content)
                    
                j = i+1
                while j<len(lines):
                    next_line = lines[j].strip()
                    
                    # if next line is empty or is the start of another label, break
                 # AI implementation here
                    # Use AI to detect if next line is another card
                    if not next_line:
                        break
                    
                    if re.match(r'^([A-Z][^:]{1,40}):\s*(.*)', next_line):
                        break
                    
                    
                    content_lines.append(next_line)
                    j+=1
                    
                full_content = ' '.join(content_lines).strip()
                
                blocks.append({
                    'type': 'labeled',
                    'label': label,
                    'content': full_content
                })
                i=j # jump past the lines we checked
                
            # if not a label
            else:    
                para_lines=[line]
                j = i+1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if not next_line:
                        break
                        
                    if re.match(r'^([A-Z][^:]{1,40}):\s*(.*)', next_line):
                        break
                    
                    para_lines.append(next_line)
                    j += 1
                    
                blocks.append({
                    'type': 'paragraph',
                    'content': ' '.join(para_lines).strip()
                })
                i=j
        return blocks
            
        
    def split_sentences(self, text: str) -> list[str]:
        paragraphs=text.split('\n\n')
        
        sentences=[]
        for para in paragraphs:
            para=para.strip()
            
            # check if empty
            if not para:
                continue    
            
            #use nltk tokenizer (sent_tokenize) to handle abbreviation, decimals, etc.
            sentences.extend(sent_tokenize(para))
            # 'extend' add multiple items, not creating 2d list

        # return using list comprehension
        # consider removing \/
        return [
            s.strip() 
            for s in sentences 
            # removes sentences less than 10 characters in length, prob not useful for flashcard
            if len(s.strip())>10
        ]

    # return the types of cards, identify cards
    def classify_sentence(self, sentence: str) -> str:
        s=sentence.strip()
        
        if s.endswith('?'):
            return 'question'
        
        words = s.lower().split()
        if words and words[0] in self.QUESTION_STARTERS:
            return 'question'
        
        for pattern in self.DEFINITION_PATTERNS:
            if re.match(pattern, s, re.IGNORECASE):
                return 'definition'
        
        return 'fact'
    
    def sentence_to_flashcard(self, sentence: str) -> dict | None:
        kind = self.classify_sentence(sentence)
        
        if kind == 'question':
            # Since we don't have enough information to generate a flashcard from a question alone, we handle it at next step
            return None
        
        if kind == 'definition':
            # regex format:
            for pattern in self.DEFINITION_PATTERNS:  
                # 'match' becomes a match object if sentence fit the exact 'pattern'
                # 'match' object is very useful for language processing
                # it allows for method  match.group() which automatically breaks up 
                match = re.match(pattern, sentence, re.IGNORECASE)
                if match:
                    return{
                        'front':f'What is {match.group(1).strip()}?',
                        'back':match.group(2).strip().rstrip('.')
                        # rstrip('.') removes the period at the end
                    }
                        
        if kind == 'definition':
            return self.make_cloze(sentence)

        return None
    
    
    
    def make_cloze(self,sentence:str) -> dict:
        words = sentence.split()
        
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'in', 'of', 'and', 'or'}
        candidates = [
            # enumerate tracks the index and value of items
            # 'i': the index position
            # 'w': the word
            # (i,w) stores in a candidate pair
            (i, w) for i, w in enumerate(words)
            # skips words less than 4 in less, avoid unimportant words
            if len(w) > 4 and w.lower().rstrip('.,') not in stop_words
        ]
        
        # catchs exceptions
        if not candidates:
            return {'front': sentence, 'back': '(no blank found)'}    
        
        
        # main areas of replacement for AI
        # currently only uses the last candidate in list
        # potentially implement AI to check accuracy
        # AI implementation here
        idx, word =  candidates[-1]
        clean_word = word.rstrip('.,;')
        blanked = words.copy()
        blanked[idx] = '_______'
        return {
            # joins combines list of strings back into 1 string
            'front': ' '.join(blanked),
            'back': clean_word
        }    
        
        
    # deal with questions what is followed by an answer sentence
    # act as the main function of the program
    def extract_flashcards(self, raw_text: str) -> list[dict]:
        """ The main function of the program
        
        Args:
            raw_text: bulk input from user (cleaned)
            
        Returns:
            list of dictionary
                The dictionary contains the front and back of a flashcard
            
        """

        # identify label/defintion pairs before spliting into sentences
        self.blocks = self.colon_pattern(raw_text)
        
        sentences = self.split_sentences(paragraph)
        cards = []
        
        for block in self.blocks:
            if block['type']=='labeled':
                label = block['label']
                content = block['content']
                
                if content:
                    cards.append({
                        'front': F"What is a {label}?",
                        'back': content
                    })
                else:
                    print(f"Warning: label '{label}' has no content")
                    
            elif block['type'] == 'paragraph':
                # follows previous identification stratagy
                i=0
                while i<len(sentences):
                    s = sentences[i]
                    kind = self.classify_sentence(s)
                    
                    if kind == 'question' and i+1<len(sentences):
                        cards.append({
                            'front': s,
                            'back': sentences[i+1]
                        })
                        i+=2
                        continue
                    
                    card = self.sentence_to_flashcard(s)
                    if card:
                        cards.append(card)
                
                    i +=1
        return cards
    
if __name__ =="__main__":
    app=FlashCardApp()
    

    





