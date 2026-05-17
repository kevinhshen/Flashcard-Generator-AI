import os
import time
print("PID:", os.getpid())

print("Hello World")
print("Please input your notes line by line in the format (front - back)")
print("Type 'stop' to finish")
print("")
print("Example: ")
print("Velocity - speed with direction")
print("Carbon - 4 valence electrons")
print("")

inputList=[]

numCard=1
while True:
    
    value = input("Card #"+str(numCard)+": ");
    if(value.lower() == "stop"):
        break
    
    if "-" not in value:
        print("Invalid format. Use: front - back")
        print("")
        continue
    
    front, back = value.split("-", 1)

    front = front.strip()
    back = back.strip()

    if front == "" or back == "":
        print("Invalid format. Missing front or back.")
        print("")
        continue

    inputList.append((front, back))
    numCard+=1
    
fileName = f"ankiImport_{int(time.time())}.txt"

with open(fileName,"w") as file:
    for front, back in inputList:
        file.write(f"{front}    {back}\n");
        
print("Saved to: "+fileName)
print("File Created, seperater by tab")

        
    
    
    



    
    




