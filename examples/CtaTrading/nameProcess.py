class A():
    def __init__(self,name):
        self.name = name
        self.info = "我是" + self.name + "号实例。"
    def output_info(self):
        print(self.info)
        
names = locals()

nums = list(range(5))
for num in nums:
    name = input("给实例取个名字：")
    names['x%s'%num] = A(name)
    # ~ name = input("给变量取个名字：")
    # ~ names['x%s'%num] = num**num

for num in nums:
    names['x%s'%num].output_info()
