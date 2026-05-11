def encode_to_dna(data: str) -> str:
    mapping = {'00':'A','01':'C','10':'G','11':'T'}
    binary = ''.join(format(ord(c), '08b') for c in data)
    dna = ''.join(mapping[binary[i:i+2]] for i in range(0, len(binary), 2))
    return dna
