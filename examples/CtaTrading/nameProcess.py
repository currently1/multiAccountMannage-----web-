class A():
    def __init__(self,name):
        self.name = name
        self.info = "����" + self.name + "��ʵ����"
    def output_info(self):
        print(self.info)
        
names = locals()

nums = list(range(5))
for num in nums:
    name = input("��ʵ��ȡ�����֣�")
    names['x%s'%num] = A(name)
    # ~ name = input("������ȡ�����֣�")
    # ~ names['x%s'%num] = num**num

for num in nums:
    names['x%s'%num].output_info()
