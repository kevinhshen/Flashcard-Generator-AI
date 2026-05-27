import os
import re
import nltk
import time
import csv

class FlashCardApp():
    def __init__(self):
        self.rawLines=[]
        self.blocks=[]
        self.seperaterList = ("-","|",":",";",",","  ","_","\n")
        
        self.introText()
        self.userInput()
        self.tokeniseData()
        self.displayList(blocks)
    
        
        
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
        
    def userInput(self):
        print("Please paste your notes here:")
        print("Type 'END' to finish input.")
        while True:
            line = input()
            if line=="END":
                break
            self.rawLines.append(line)
    
    def tokeniseData(self):
        #This function aims to tokenise the user input into blocks of text
        for line in self.rawLines:
            for seperater in self.seperaterList:
                self.blocks.append(line.split(seperater))
            
    def displayList(self, arr):
        for item in arr:
            print(item)
            
    def clean_text(text: str) -> str:
        #Converts newline formats with different OS into standard \n
        text = text.replace('\r\n', '\n').replace('\r', '\n') 

        #Collapse multiple empty space into one
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Fix spaces around punctuation
        text = re.sub(r'\s+([?.!,])', r'\1', text)
        
        # Collapse multiple spaces
        text = re.sub(r'[^\S\n]+', ' ', text)
        
        return text.strip()
        
            



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

        




    
    




