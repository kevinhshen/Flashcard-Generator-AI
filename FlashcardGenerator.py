import os
import time
import csv

inputList=[]
seperaterList = ("-","|",":",";",",","  ","_")
numCard=1

def introText():
    print("PID:", os.getpid())
    print("Hello World")
    print("Please input your notes line by line in the format (front - back)")
    print("Type 'stop' to finish")
    print("")
    print("Example: ")
    print("Velocity - speed with direction")
    print("Carbon - 4 valence electrons")
    print("")
    
introText()


while True:
    
    value = input("Card #"+str(numCard)+": ");
    if(value.lower() == "stop"):
        break
    
    if "-" not in value:
        print("Invalid format. Use: front - back")
        print("")
        continue
    
    bestSeperater="" 
    topScore=0
    for seperater in seperaterList:
        score=0
        line = value.split(seperater)
        
        if len(line)==2:
            score+=2;
        
        if len(line)!=2:
            score-=1;
            
        front = line[0].strip()
        back = line[1].strip()
        
        if not front or not back:
            score-=2;
            
        if score>topScore:
            topScore=score
            bestSeperater=seperater
        
    front, back = value.split(bestSeperater,1)

    if front == "" or back == "":
        print("Invalid format. Missing front or back.")
        print("")
        continue

    inputList.append((front, back))
    numCard+=1
    
fileName = f"ankiImport_{int(time.time())}.csv"

with open(fileName,"w", newline="") as file:
    writer = csv.writer(file)
    for front, back in inputList:
        writer.writerow([front, back])
        
print("Saved to: "+fileName)
print("File Created, seperater by tab")

        




    
    




