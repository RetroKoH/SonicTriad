
class Compress():
    def __init__(self, data_input):
        self.data_input = self.set_input(data_input)
        self.output = []
        self.bit_buffer = 0
        self.bit_count = 0

    ######################################
    # Set input data                     #
    ######################################
    # ARGUMENTS:                         #
    #     data - Input data              #
    # (bytes, bytearray, or iterable of  #
    # byte values)                       #
    #     position - Input data position #
    ######################################
    def set_input(self, data_input):
        if isinstance(data_input, (int, str)):
            raise TypeError("Input must be bytes or an iterable of byte values.")
        return bytes(data_input)

    ########################
    # Write byte           #
    ########################
    # ARGUMENTS:           #
    #     value - output   #
    #                      #
    # (Keep low 8 bits)    #
    #                      #
    # RETURNS:             #
    #     N/A              #
    ########################
    def write_byte(self, value):
        self.output.append(value & 0xFF)

    ########################
    # Write word           #
    ########################
    # ARGUMENTS:           #
    #     value - output   #
    #                      #
    # (Write low 16 bits,  #
    #  high byte first)    #
    #                      #
    # RETURNS:             #
    #     N/A              #
    ########################
    def write_word(self, value):
        self.write_byte(value >> 8)
        self.write_byte(value)

    #####################################
    # Write bits                        #
    #####################################
    # ARGUMENTS:                        #
    #     value - Value to write        #
    #     bits - bit count of value     #
    #                                   #
    # See: WriteBits()                  #
    #####################################
    def write_bits(self, value, bits):
        # Shift buffer to make room for the new value
        self.bit_buffer = (self.bit_buffer << bits) | value
        # Add to bit count
        self.bit_count += bits

        # Write completed bytes
        while self.bit_count >= 8:
            self.bit_count -= 8
            self.write_byte(self.bit_buffer >> self.bit_count)

        # Remove the written bits, retaining pending low bits only
        self.bit_buffer &= (1 << self.bit_count) - 1

    #####################################
    # Flush bits                        #
    #####################################
    # Finishes the partially filled     #
    # byte left by write_bits()         #
    #                                   #
    # 0–7 pending bits flushed          #
    # If 0, this does nothing           #
    #                                   #
    # See: the end of EmitCodes()       #
    #####################################
    def flush_bits(self):
        if self.bit_count:
            self.write_byte(self.bit_buffer << (8 - self.bit_count))


#############################################
# Nemesis compression class                 #
# Huffman-based Nemesis compression         #
#############################################
""" Notes:
- compute_best_codes() explicitly considers an all-inline baseline and a single-symbol candidate.
  It evaluates codes after reserved-prefix adjustment; Clownacy chooses candidate lengths before that adjustment.
- compute_code_lengths() uses deterministic symbol-number tie-breaking. Clownacy’s CompareNodes() compares only
  occurrence counts, and qsort() does not guarantee stable ordering.
- encoded_size() includes the constant three-byte header/terminator overhead. Clownacy omits that constant from its
  size comparison.
- write_bits() corresponds to both WriteBits() and WriteBit(), since your function also performs buffering
  and byte emission.
"""

class Nemesis(Compress):
    INLINE_PREFIX = 0b111111

    def compress(self, xor_mode = None):
        size = len(self.data_input)

        # Reject empty or invalid input (Clownacy’s EmitHeader() checks validity; empty input check is my addition).
        # [see: EmitHeader; if (state->bytes_read % bytes_per_tile != 0)]
        if size == 0 or size % 32:
            raise ValueError("Input must be nonempty and contain complete 0x20-byte tiles.")

        # Tile count uses bits 0-14; bit 15 is XOR flag (Max 32767 tiles)
        # [see: EmitHeader; else if (total_tiles > 0x7FFF)]
        if size // 32 > 0x7FFF:
            raise ValueError("Nemesis supports at most 32767 tiles.")

        # If 'None', the mode that produces the smaller output gets used (default)
        if xor_mode is not None and type(xor_mode) is not bool:
            raise TypeError("xor_mode must be None, False, or True.")

        # Temporary
        self.output = self.data_input

        # Return compressed bytes as a list
        return self.output

    # Sub-functions


#########################
# Compression callers #
#########################

def nemesis(data, xor_mode = None):
    comp = Nemesis(data)
    return comp.compress(xor_mode)
