import os
import re

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
        self.blocks=[]
        self.tokenised=[]
        self.seperaterList = ("-","|",":",";",",","  ","_","\n")
        self.QUESTION_STARTERS = ('what', 'who', 'where', 'when', 'why', 'how', 
            'which', 'define', 'explain', 'describe', 'list'
        )
        self.DEFINITION_PATTERNS = [
            r'.+ is (a|an|the) .+',          # "X is a Y"
            r'.+ refers to .+',               # "X refers to Y"
            r'.+ is defined as .+',           # "X is defined as Y"
            r'.+ means .+',                   # "X means Y"
            r'.+, (which|who) is .+',        # "X, which is Y"
        ]

        
        self.introText()
        self.lines=self.user_input_list()
        
        for line in self.lines:
            line=self.clean_text(line)
            self.tokenised.extend(self.split_sentences(line))
        
        self.display_list(self.tokenised)
    
        
        
    def introText(self):
        print("PID:", os.getpid())
        print("Hello World")
        print("Please input your notes line by line in the format (front - back)")
        print("Type 'end' to finish")
        print("")
        print("Example: ")
        print("Velocity - speed with direction")
        print("Carbon - 4 valence electrons")
        print("")
        
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
        for item in arr:
            print("-----------------------------------------------")
            print(item)
            
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

        




    
    




