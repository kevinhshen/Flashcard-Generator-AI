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

        
        self.lines=self.user_input_list()
        
        for line in self.lines:
            self.flash_cards.extend(self.extract_flashcards(line))
        
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
        #Converts newline formats with different OS into standard \n
        text = text.replace('\r\n', '\n').replace('\r', '\n') 

        #Collapse multiple empty space into one
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Fix spaces around punctuation
        text = re.sub(r'\s+([?.!,])', r'\1', text)
        
        # Collapse multiple spaces
        text = re.sub(r'[^\S\n]+', ' ', text)
        
        return text.strip()
    
    # add before split_sentence
    # Aims to turn raw text into structured blocks, instead of splitting everything into individual sentences
    def merge_label_blocks(self, text: str)  -> list[dict]:
        # returns a list of dictionary
        lines=text.split('\n')
        blocks=[]
        i = 0
        
        while i < len(lines):
            line=lines[i].strip()
            
            # skip if line is empty
            if not line:
                i += 1
                continue
            
            # use regex for main detection
            # Pattern #1: ([A-Z][^:]{1,40})
            # [A-Z] means the label must start with a capital letter
            # [^:]{1,40} allows 1-40 non-colon ':' characters
            # because it uses {1,40}, the label must have at least 2 characters total: 
            # 'A:' would not match because it still needs 1 more character
            # '\s*' means zero or more whitespace characters after the colon
            
            # Pattern #2: (.*)
            # captures everything after the colon and optional spaces
            label_match = re.match(r'^([A-Z][^:]{1,40}):\s*(.*)', line)
            
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
    def extract_flashcards(self, text: str) -> list[dict]:
        text = self.clean_text(text)
        self.blocks = self.merge_label_blocks(text)
        sentences = self.split_sentences(text)
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
    

    

# while True:
    
#     value = input("Card #"+str(numCard)+": ");
#     if(value.lower() == "end"):
#         break
    
    
#     bestSeperater="" 
#     topScore=0
#     for seperater in seperaterList:
#         score=0
#         line = value.split(seperater)
#         if len(line) <2:
#             print("Card invalid")
#             continue
#         if len(line) == 2:
#             score += 2
#         else:
#             score -= 2

#         if line[0]=="" or line[1]=="":
#             score -= 3
            
#         front = line[0].strip()
#         back = line[1].strip()    
        
        
        
            
#         if score>topScore:
#             topScore=score
#             bestSeperater=seperater
    
#     if bestSeperater=="":
#         print("Card invalid")
#         continue
    
#     front, back = value.split(bestSeperater,1)

#     inputList.append((front, back))
#     numCard+=1
    
# fileName = f"ankiImport_{int(time.time())}.csv"

# with open(fileName,"w", newline="") as file:
#     writer = csv.writer(file)
#     for front, back in inputList:
#         writer.writerow([front, back])
        
# print("Saved to: "+fileName)
# print("File Created, seperater by tab")

        




    
    




