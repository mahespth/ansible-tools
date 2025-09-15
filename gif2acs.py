/*

   steve@m4her.con
   cobwet gif to acs for xterm

*/

from PIL import Image
import sys

# Define the ACS characters that best approximate intensity levels
# From darkest to lightest intensity in xterm ACS:
ACS_CHARS = [' ', 'a', 'x', 'm', 'l', 'k', 'q', 'j', 'u', 't', 'n', 'w']

# Map grayscale intensity to ACS characters
def map_pixel_to_acs(pixel):
    return ACS_CHARS[int(pixel / 256 * (len(ACS_CHARS) - 1))]

# Convert image to ACS characters
def convert_gif_to_acs(image_path, output_width=80):
    # Open and convert the image to grayscale
    img = Image.open(image_path).convert('L')
    
    # Calculate new height to maintain aspect ratio
    width, height = img.size
    aspect_ratio = height / width
    new_height = int(output_width * aspect_ratio * 0.5)
    img = img.resize((output_width, new_height))

    # Convert each pixel to an ACS character
    acs_data = []
    for y in range(img.height):
        row = ''.join(map_pixel_to_acs(img.getpixel((x, y))) for x in range(img.width))
        acs_data.append(row)

    return acs_data

# Print ACS representation to the terminal
def print_acs_image(acs_data):
    for row in acs_data:
        print(row)

# Main function to run the conversion
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python convert_gif_to_acs.py <image_path>")
        sys.exit(1)

    image_path = sys.argv[1]
    acs_data = convert_gif_to_acs(image_path)
    print_acs_image(acs_data)
