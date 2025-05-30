import re
import os

class MIPSCompiler:
    def __init__(self):
        self.label_table = {}
        self.temp_file = "temp_assembly.txt"
        self.output_file = "trans_code.txt"
        self.opcodes = {
            # Opcode lệnh R
            'add' : '000000', 'addu' : '000000', 'sub' : '000000', 'subu' : '000000', 
            'sll' : '000000', 'srl' : '000000', 
            'slt' : '000000', 'sltu' : '000000', 
            'jr' : '000000', 
            'and' : '000000', 'or' : '000000', 'nor' : '000000', 'xor' : '000000',
    
            # Opcode lệnh I
            'addi' : '001000', 'addiu' : '001001', 'slti' : '001010', 'sltiu' : '001011',
            'andi' : '001100', 'ori' : '001101' , 'xori' : '001110',
            'lb' : '100000',
            'lbu' : '100100',
            'lh' : '100001',
            'lhu' : '100101',
            'lw' : '100011',
            'sw' : '101011',
            'beq' : '000100', 'bne' : '000101',
            'lui' : '001111',
    
            # Opcode lệnh J
            'j': '000010', 'jal': '000011'
        }
        #Funtions (Nhóm lệnh R)
        self.funct_codes = {
            'add': '100000', 'addu' : '100001', 'sub': '100010', 'subu' : '100011',
            'and': '100100', 'or': '100101', 'xor' : '100110', 'nor' : '100111',
            'sll': '000000', 'srl': '000010', 
            'slt' : '101010', 'sltu' : '101011',
            'jr': '001000', 'jalr' : '001001'
        }
        #Thanh ghi
        self.registers = {
            '$zero': '00000', '$at': '00001',
            '$v0': '00010', '$v1': '00011',
            '$a0': '00100', '$a1': '00101', '$a2': '00110', '$a3': '00111',
            '$t0': '01000', '$t1': '01001', '$t2': '01010', '$t3': '01011',
            '$t4': '01100', '$t5': '01101', '$t6': '01110', '$t7': '01111',
            '$s0': '10000', '$s1': '10001', '$s2': '10010', '$s3': '10011',
            '$s4': '10100', '$s5': '10101', '$s6': '10110', '$s7': '10111',
            '$t8': '11000', '$t9': '11001',
            '$k0': '11010', '$k1': '11011',
            '$gp': '11100', '$sp': '11101', '$fp': '11110', '$ra': '11111'
        }
        
    def delete_comment(self, line):
        #Xóa các chú thích khỏi dòng lệnh
        comment_pos = line.find('#')
        if comment_pos != -1:
            line = line[:comment_pos]
        return line.strip()
    
    def calculate_immediate(self, value, current_pc=0):
        #Tính toán giá trị immediate cho branch instructions
        if isinstance(value, str) and value in self.label_table:
            # Tính offset cho branch (word addressing)
            return (self.label_table[value] - current_pc - 1)
        return value
    
    def build_label_table(self, lines):
        #Xây dựng bảng label và xóa label khỏi các dòng lệnh
        cleaned_lines = []
        address = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Kiểm tra xem có label không
            if ':' in line:
                parts = line.split(':', 1)
                label = parts[0].strip()
                
                # Nếu có instruction sau label trên cùng dòng
                if len(parts) > 1 and parts[1].strip():
                    self.label_table[label] = address
                    cleaned_lines.append(parts[1].strip())
                    address += 1
                else:
                    # Label đứng một mình, địa chỉ là instruction tiếp theo
                    self.label_table[label] = address
            else:
                cleaned_lines.append(line)
                address += 1
                
        return cleaned_lines
    
    def parse_instruction(self, instruction):
        #Phân tích cú pháp lệnh
        parts = instruction.replace(',', ' ').split()
        opcode = parts[0]
        operands = parts[1:] if len(parts) > 1 else []
        return opcode, operands
    
    def generate_r_type(self, opcode, operands):
        #Tạo mã nhị phân cho lệnh loại R
        rs = '00000'
        rt = '00000'
        rd = self.registers[operands[0]]
        shamt = '00000'
        funct = self.funct_codes[opcode]
        
        if opcode == 'jr':
            rs = self.registers[operands[0]]
            rd = '00000'
        elif opcode in ['sll', 'srl']:
            rd = self.registers[operands[0]]
            rt = self.registers[operands[1]]
            shamt = format(int(operands[2]), '05b')
        else:
            rd = self.registers[operands[0]]
            rs = self.registers[operands[1]]
            rt = self.registers[operands[2]]
        
        return f"{self.opcodes[opcode]}{rs}{rt}{rd}{shamt}{funct}"
    
    def generate_i_type(self, opcode, operands, current_pc=0):
        #Tạo mã nhị phân cho lệnh loại I
        op = self.opcodes[opcode]
        
        if opcode == 'lui':
            # lui rt, immediate
            rt = self.registers[operands[0]]
            immediate = int(operands[1], 16) if operands[1].startswith('0x') else int(operands[1])
            return f"{op}00000{rt}{format(immediate & 0xFFFF, '016b')}"
        
        elif opcode in ['lw', 'sw', 'lbu', 'lhu']:
            # lw/sw rt, offset(base)
            rt = self.registers[operands[0]]
            # Parse offset(base)
            offset_base = operands[1]
            if '(' in offset_base:
                offset, base = offset_base.split('(')
                base = base.rstrip(')')
                offset = int(offset) if offset else 0
                rs = self.registers[base]
            else:
                offset = int(offset_base)
                rs = '00000'
            return f"{op}{rs}{rt}{format(offset & 0xFFFF, '016b')}"
        
        elif opcode in ['beq', 'bne']:
            # beq rs, rt, label/offset
            rs = self.registers[operands[0]]
            rt = self.registers[operands[1]]
            if operands[2] in self.label_table:
                offset = self.calculate_immediate(operands[2], current_pc)
            else:
                offset = int(operands[2])
            return f"{op}{rs}{rt}{format(offset & 0xFFFF, '016b')}"
        
        else:
            # addi, addiu, andi rt, rs, immediate
            rt = self.registers[operands[0]]
            rs = self.registers[operands[1]]
            immediate = int(operands[2], 16) if operands[2].startswith('0x') else int(operands[2])
            return f"{op}{rs}{rt}{format(immediate & 0xFFFF, '016b')}"
    

    def generate_j_type(self, opcode, operands, current_pc=0):
        #Tạo mã nhị phân cho lệnh loại J
        op = self.opcodes[opcode]
        
        # PC ban đầu của text segment trong MIPS
        base_pc = 0b0000010000000000000000000000
        
        if operands[0] in self.label_table:
            # Tính địa chỉ từ label table: base_pc + (instruction_index * 4)
            address = (base_pc + (self.label_table[operands[0]] * 4)) >> 2
        else:
            # Địa chỉ trực tiếp
            address = int(operands[0]) >> 2
        
        # Chỉ lấy 26 bit thấp nhất cho J-type instruction
        return f"{op}{format(address & 0x3FFFFFF, '026b')}"
    
    def generate_binary(self, instruction, current_pc=0):
        opcode, operands = self.parse_instruction(instruction)
        if opcode in self.funct_codes:
            return self.generate_r_type(opcode, operands)
        elif opcode in self.opcodes:
            if opcode in ['j', 'jal']:
                return self.generate_j_type(opcode, operands, current_pc)
            else:
                return self.generate_i_type(opcode, operands, current_pc)
        else:
            raise ValueError(f"Unknown instruction: {opcode}")

    def first_pass(self, input_file):
        #Chuyến 1: Xử lý chú thích, label và tạo file tạm
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Bước 1.1: Loại bỏ chú thích và dòng trống
        cleaned_lines = []
        for line in lines:
            line = self.delete_comment(line)
            if line:
                cleaned_lines.append(line)
        
        # Bước 1.2 & 1.3: Xây dựng bảng label và loại bỏ label
        processed_lines = self.build_label_table(cleaned_lines)
        
        # Ghi file tạm
        with open(self.temp_file, 'w') as f:
            for line in processed_lines:
                f.write(line + '\n')
        
        return processed_lines
    
    def second_pass(self, processed_lines):
        #Chuyến 2: Tạo mã máy từ file tạm
        machine_codes = []
        
        for pc, instruction in enumerate(processed_lines):
            if instruction.strip():
                try:
                    binary_code = self.generate_binary(instruction.strip(), pc)
                    machine_codes.append(binary_code)
                except Exception as e:
                    print(f"Error processing instruction '{instruction}': {e}")
                    continue
        
        # Ghi file đầu ra
        with open(self.output_file, 'w') as f:
            for code in machine_codes:
                f.write(code + '\n')
        
        return machine_codes
    
    def compile(self, input_file):
        #Hàm chính - biên dịch chương trình assembly
        print("Starting MIPS Assembly to Machine Code compilation...")
        
        # Chuyến 1
        print("Pass 1: Processing comments, labels, and building symbol table...")
        processed_lines = self.first_pass(input_file)
        print(f"Label table: {self.label_table}")
        
        # Chuyến 2  
        print("Pass 2: Generating machine code...")
        machine_codes = self.second_pass(processed_lines)
        
        print(f"Compilation completed! Output written to {self.output_file}")
        print(f"Generated {len(machine_codes)} machine code instructions.")
        
        # Hiển thị kết quả
        for code in machine_codes:
            print(code)
        
        # Cleanup
        if os.path.exists(self.temp_file):
            os.remove(self.temp_file)
        
        return machine_codes

def main():
    #Hàm chính của chương trình"""
    compiler = MIPSCompiler()
    
    # Sử dụng file test_case.txt từ document
    input_file = "test_case.txt"
    
    try:
        # Biên dịch
        machine_codes = compiler.compile(input_file)
        
        print(f"\nCompilation successful! Check {compiler.output_file} for the complete machine code.")
        
    except Exception as e:
        print(f"Compilation failed: {e}")

if __name__ == "__main__":
    main()
