

print("Hello World")
print("Please input your notes line by line in the format (front - back)")
print("Type 'stop' to finish")
print("")
print("Example: ")
print("Velocity - speed with direction")
print("Carbon - 4 valence electrons")
print("")

inputList=[]

numCard=0
while True:
    numCard+=1
    value = input("Card #"+str(numCard)+": ");
    if(value.lower() == "stop"):
        break
    
    if "-" not in value:
        print("Invalid format. Use: front - back")
        continue
    
    front, back = value.split("-", 1)

    front = front.strip()
    back = back.strip()

    if front == "" or back == "":
        print("Invalid format. Missing front or back.")
        continue

    inputList.append((front, back))
    




