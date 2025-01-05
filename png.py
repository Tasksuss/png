import zlib
"""
Disclaimer: This program is designed to be run on a Python 3.11.4 interpreter. It is specially written to satisfy the 
specifications outlined for the module assignment, where many additional error checking and exceptions could be added
to make this code more robust. However, for the sake of program efficiency they were not included; This is a deliberate
choice and not the author's negligence. It is meant to run as fast as possible while being false-proof, not fool-proof.
"""
class PNG:
    def __init__(self):
        # Initialising the attributes
        self.data = b''
        self.info = ''
        self.width = int(0)
        self.height = int(0)
        self.bit_depth = int(0)
        self.color_type = int(0)
        self.compress = int(0)
        self.filter = int(0)
        self.interlace = int(0)
        self.img = []

    def load_file(self, file_name):
        # Load the raw data and handle the File Not Found exception
        try:
            with open(file_name, 'rb') as file:
               self.data = file.read()
               self.info = file_name
        except FileNotFoundError:
            self.data = b''
            self.info = 'file not found'
            raise 

    def valid_png(self):
        # String determination
        signature = b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A'     # Binary form of the signature
        data_signature = self.data[:8]
        return signature == data_signature

    def read_header(self):
        # Load from self.data the IHDR chunk, then parse and distribute attributes accordingly
        start = self.data.find(b'IHDR')
        ihdr_start = start + 4      # Jump ahead the b'IHDR'
        ihdr_data = self.data[ihdr_start:ihdr_start+13]
        # Update attributes
        self.width = int.from_bytes(ihdr_data[:4], 'big')
        self.height = int.from_bytes(ihdr_data[4:8], 'big')
        self.bit_depth = ihdr_data[8]
        self.color_type = ihdr_data[9]
        self.compress =  ihdr_data[10]
        self.filter = ihdr_data[11]
        self.interlace = ihdr_data[12]

    def read_chunks(self):
        """
        This method first traverse the self.data and then decompress/read pixel data line by line. Eventually append
        to self.img attribute. Only information stored in IDAT chunks is of our interest for this assignment.So,the
        rest of the ancillary chunks are ignored and skipped ahead whilst traversing the self.data.
        """
        idat_chunk = []     # There may be several idat_chunk present
        position = 33        # Set the pointer after the IHDR

        while position < len(self.data):
            if position + 8 > len(self.data):       # Ensure enough bytes are left for length and type
                raise ValueError("Incomplete chunk found in the file.")
            length = int.from_bytes(self.data[position:position + 4], 'big')    # Read the chunk length and type
            position += 4       # Keep updating the pointer
            chunk_type = self.data[position:position + 4].decode('ascii')
            position += 4

            # Only copy the data if it is a IDAT chunk
            if chunk_type == 'IDAT':
                if position + length > len(self.data):
                    raise ValueError("Incomplete IDAT chunk.")
                chunk_data = self.data[position:position + length]
                idat_chunk.append(chunk_data)
                position += length  # Move the pointer by the chunk length
            else:
                position += length      # Jump ahead by length if encounter other chunk
            position += 4       # Skip the CRC for now
            if chunk_type == 'IEND':
                break

        binary_idat = b''.join(idat_chunk)      # Concatenate multiple idat_chunks
        raw_data = zlib.decompressobj().decompress(binary_idat)  # Memory allocation and LZ77/Huffman decoding using zlib
        row_length = 1 + self.width * 3         # Scanline length and structure: 'F r g b r g b...' (3n+1)
        upper_row = [0] * (self.width * 3)      # Initialise the upper_row for padding

        for i in range(0, len(raw_data), row_length):
            if i + row_length > len(raw_data):
                raise ValueError("Unexpected end of scanline data.")
            filter_type = raw_data[i]       # First byte indicates filter type
            current_row = raw_data[i + 1:i + row_length]
            decoded_row = PNG.inverse_filter(current_row, upper_row, filter_type)       # See the staticmethod below
            row_pixel = [decoded_row[j:j + 3] for j in range(0, len(decoded_row), 3)]   # Convert to RGB triplets
            self.img.append(row_pixel)
            upper_row[:] = decoded_row      # Update upper_row for the next iteration

    @staticmethod
    def inverse_filter(current_row, upper_row, filter_type):
        """
        This static method take the current and upper row and reverse the filtering effect indicated by the filter_type.
        Consisting of 5 types of filter: No filter, Left subtraction, Up subtraction, Averaging and Paeth filter.
        """
        row_length = len(current_row)
        reconstructed_row = [0] * row_length  # Initialize reconstructed_row as a list

        # 1st Type: No filter
        if filter_type == 0:
            return current_row

        # 2nd Type: Left subtraction filter
        # Need to set the step size to 3 since colour channels are independent
        elif filter_type == 1:
            for i, current_value in enumerate(current_row):
                    left = reconstructed_row[i - 3] if i >= 3 else 0
                    reconstructed_row[i] = (current_value + left) % 256     # Always take the 2^8 modulus afterward

        # 3rd Type: Up subtraction filter
        elif filter_type == 2:
            reconstructed_row = [(current_row[i] + upper_row[i]) % 256 for i in range(row_length)]

        # 4th Type: Average filter
        elif filter_type == 3:
            for i in range(row_length):
                left = reconstructed_row[i - 3] if i >= 3 else 0
                up = upper_row[i]
                reconstructed_row[i] = (current_row[i] + (left + up) // 2) % 256

        # 5th Type: Paeth filter
        elif filter_type == 4:
            for i in range(row_length):
                left = reconstructed_row[i - 3] if i >= 3 else 0
                up = upper_row[i]
                upper_left = upper_row[i - 3] if i >= 3 else 0
                p = left + up - upper_left
                pa = abs(p - left)
                pb = abs(p - up)
                pc = abs(p - upper_left)
                predictor = left if pa <= pb and pa <= pc else (up if pb <= pc else upper_left)
                reconstructed_row[i] = (current_row[i] + predictor) % 256
        return reconstructed_row

    def save_rgb(self, file_name, rgb_option):
        """"
        Saved file structure: Sig + IHDR + IDAT + IEND
        IHDR = length (4) + IHDR (4) + img_info (9) + CRC (4)
        IDAT = length (4) + IDAT (4) + data (length) + CRC (4)
        IEND = length (4) + IEND (4) + CRC (4)
        Assumed 0 type filtering throughout for this assignment to ensure efficiency. Although a better and more
        practical encoding is achieved through the Adaptive Filtering Scheme, which is not implemented here.
        """
        # 1st Step: Write the signature
        raw_rgb_file = bytearray(b'\x89PNG\r\n\x1a\n')

        # 2nd Step: Tailor the IHDR using self.attributes
        ihdr_data = (self.width.to_bytes(4, 'big') + self.height.to_bytes(4, 'big') +
                     self.bit_depth.to_bytes(1, 'big') + self.color_type.to_bytes(1, 'big') +
                     self.compress.to_bytes(1, 'big') + self.filter.to_bytes(1, 'big') +
                     self.interlace.to_bytes(1, 'big'))     # Prepare the IHDR chunk data
        ihdr_length = len(ihdr_data).to_bytes(4, 'big')
        raw_rgb_file.extend(ihdr_length)
        raw_rgb_file.extend(b'IHDR')
        raw_rgb_file.extend(ihdr_data)
        raw_rgb_file.extend(PNG.cal_crc(b'IHDR', ihdr_data).to_bytes(4, 'big'))

        # 3rd Step: Make the IDAT chunk from self.img
        scanlines = bytearray()     # Initialise a bytearray to store pixel data more efficiently
        for row in self.img:
            scanline = bytearray([0])  # Filter type 0
            zero_channel = [rgb_option % 3, (rgb_option + 1) % 3]   # Mod 3 to select the channels
            for pixel in row:
                pixel[zero_channel[0]] = 0  # Zero out the specified channel
                pixel[zero_channel[1]] = 0  # Zero out the next channel
                scanline.extend(pixel)
            scanlines.extend(scanline)

        compressed_idat = zlib.compressobj().compress(scanlines)
        idat_length = len(compressed_idat).to_bytes(4, 'big')
        raw_rgb_file.extend(idat_length)
        raw_rgb_file.extend(b'IDAT')
        raw_rgb_file.extend(compressed_idat)    # See staticmethod
        raw_rgb_file.extend(PNG.cal_crc(b'IDAT', compressed_idat).to_bytes(4, 'big'))

        # 4th Step: Make the IEND chunk
        iend_length = (0).to_bytes(4, 'big')
        raw_rgb_file.extend(iend_length)
        raw_rgb_file.extend(b'IEND')
        raw_rgb_file.extend(PNG.cal_crc(b'IEND', b'').to_bytes(4, 'big'))

        # 5th Step: Write the raw_rgb_file into a file named 'file_name'
        with open(file_name, 'wb') as file:
            file.write(raw_rgb_file)

    @staticmethod
    def cal_crc(chunk_type, chunk_data):
        # This static method takes two args (chunk_type & chunk_data) to calculate for the Cyclic Redundancy Check
        input = chunk_type + chunk_data
        return zlib.crc32(input)
