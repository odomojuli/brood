# User Input
rows_input = input("Enter length of frequency: ")
columns_input = input("Enter number of cycles: ")

# Type Cast into Integer
rows_value = int(rows_input)
columns_value = int(columns_input)

table_range = list(list(range(1*i,(rows_value+1)*i, i)) for i in range(1,columns_value+1))
for i in table_range:
    i = [str(j).rjust(len(str(table_range[-1][-1]))+1) for j in i]
    print(''.join(i))
