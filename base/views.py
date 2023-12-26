from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from .forms import EncodeImageForm, DecodeImageForm, RegistrationForm, LoginForm
from .models import steganography, UserRegistration
from django.conf import settings

from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.http import Http404 

# Required libraries for image processing
import os
from PIL import Image
import numpy as np
from django.core.files import File
import logging
from django.contrib.auth import logout


    # Redirect to a success page.
# import imageio

# ----------Authentication and authorization views---------------
# register view
def registerUser(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            profile_picture = form.cleaned_data.get('profile_picture')
            email = form.cleaned_data.get('email')
            user_registration = UserRegistration(user=user, profile_picture=profile_picture, email=email)
            user_registration.save()
            login(request, user)
            # username = user.username
            return redirect('home')
    else:
        form = RegistrationForm()
    return render(request, 'base/SignUp.html', {'form': form})


# login view
def loginUser(request):
    error_message = None
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)
                return redirect('landing')
            else:
                error_message = "Invalid username or password."

    else:
        form = LoginForm()

    return render(request, 'base/SignIn.html', {'form': form, 'error_message': error_message})

# logout view
def logout_view(request):
    try:
        logout(request)
    except Exception as e:
        return Http404('Page not found', e)

    return render(request, 'base/home.html')

# Landing Page view
def home(request):
    return render(request, 'base/home.html')


# ----------Image Steganography--------------------
# Rail Fence Enc
def encrypt_rail_fence(text, key):
    rail = [['\n' for _ in range(len(text))] for _ in range(key)]
    dir_down = False
    row, col = 0, 0

    for char in text:
        if row == 0 or row == key - 1:
            dir_down = not dir_down
        rail[row][col] = char
        col += 1
        row = row + 1 if dir_down else row - 1

    result = ''.join(char for row in rail for char in row if char != '\n')
    return result



# Rail Fence Dec
def decrypt_rail_fence(cipher, key):
    rail = [['\n' for _ in range(len(cipher))] for _ in range(key)]
    dir_down = False
    row, col = 0, 0

    for _ in range(len(cipher)):
        if row == 0:
            dir_down = True
        if row == key - 1:
            dir_down = False
        rail[row][col] = '*'
        col += 1
        row = row + 1 if dir_down else row - 1

    index = 0
    for i in range(key):
        for j in range(len(cipher)):
            if rail[i][j] == '*' and index < len(cipher):
                rail[i][j] = cipher[index]
                index += 1

    result = ''
    row, col = 0, 0
    for _ in range(len(cipher)):
        if row == 0:
            dir_down = True
        if row == key - 1:
            dir_down = False
        if rail[row][col] != '*':
            result += rail[row][col]
            col += 1
        row = row + 1 if dir_down else row - 1

    return result



# Encoding Image
logger = logging.getLogger('base')

def encode_image(request):
    media_root = settings.MEDIA_ROOT
    success_message = ""
    error_message = ""
    if request.method == 'POST':
        form = EncodeImageForm(request.POST, request.FILES)
        if form.is_valid():
            # Get the form data
            image = request.FILES['image']
            message = form.cleaned_data['message']
            password = form.cleaned_data['password']
            dest = form.cleaned_data['dest']
            receiver = form.cleaned_data['receiver']
            sender = request.user

            # --ASCII Encryption - Level 1
            encmsg = ""
            for ch in message:
                asc = ord(ch) + 3
                ench = chr(asc)
                encmsg += ench
            
            # Rail Fence encryption - Level 2
            encrypted = encrypt_rail_fence(encmsg, 3)

            # save the instance of steg model
            encoded_image = steganography(image=image, message=encrypted, dest=dest, receiver=receiver, sender=sender)
            encoded_image.save()
            
            # Encode the image
            image_path = os.path.join(media_root, 'originalImages', image.name)
            encoded_image_path = os.path.join(media_root, 'stegoImages', dest)

            # Get the original image's path: used to update the record afterwards
            original_image_path = os.path.normpath(os.path.join('originalImages', image.name)).replace("\\", "/")
            # print(f"Original image path: {original_image_path}")

            try:
                img = Image.open(image_path)
                width, height = img.size
                array = np.array(list(img.getdata()))

                if img.mode == 'RGB':
                    n = 3
                elif img.mode == 'RGBA':
                    n = 4

                total_pixels = array.size // n

                encrypted += password
                b_message = ''.join([format(ord(i), "08b") for i in encrypted])
                req_pixels = len(b_message)

                if req_pixels > (total_pixels * 3):
                    return render(request, 'error.html', {'message': 'ERROR: Need larger file size'})

                index = 0
                for p in range(total_pixels):
                    for q in range(0, 3):
                        if index < req_pixels:
                            array[p][q] = int(bin(array[p][q])[2:9] + b_message[index], 2)
                            index += 1

                array = array.reshape(height, width, n)
                enc_img = Image.fromarray(array.astype('uint8'), img.mode)
                enc_img.save(encoded_image_path)
                
                # Update the 'encoded_img' field based on the original image path
                try:
                    original_image = steganography.objects.get(image=original_image_path)
                except steganography.DoesNotExist:
                    return render(request, 'base/error.html', {'message': f'Original image not found: {original_image_path}'})

                # Update the 'encoded_img' field with the path of the encoded image
                encoded_img_rel_path = os.path.relpath(encoded_image_path, media_root)
                original_image.encoded_img = encoded_img_rel_path
                original_image.save()
                # return redirect('success')
                success_message = "Image encoding was successful."
            except Exception as e:
                # logger.error(str(e))
                # return render(request, 'base/error.html', {'message': str(e)})
                error_message = str(e)
    else:
        form = EncodeImageForm()

    return render(request, 'base/encodeImg.html', {'form': form, 'success_message': success_message, 'error_message': error_message})

# decode image view
# def decode_image(request):
#     user = request.user
#     steg_records = steganography.objects.filter(receiver=user).order_by('-created')
#     message = ""
#     error_message = ""

#     if request.method == 'POST':
#         form = DecodeImageForm(request.POST, request.FILES)

#         if form.is_valid():
#             # encoded_image = request.FILES['encoded_image']
#             # password = form.cleaned_data['password']
#             password = request.POST.get('password')
#             image_url = request.POST.get('image_url')

#             try:
#                 # img = Image.open(encoded_image)
#                 # new line added
#                 image = File(open(image_url, 'rb'))
#                 img = Image.open(image)

#                 array = np.array(list(img.getdata()))

#                 if img.mode == 'RGB':
#                     n = 3
#                 elif img.mode == 'RGBA':
#                     n = 4

#                 total_pixels = array.size // n

#                 hidden_bits = ""
#                 for p in range(total_pixels):
#                     for q in range(0, 3):
#                         hidden_bits += (bin(array[p][q])[2:][-1])

#                 hidden_bits = [hidden_bits[i:i+8] for i in range(0, len(hidden_bits), 8)]

#                 hiddenmessage = ""
#                 for i in range(len(hidden_bits)):
#                     x = len(password)
#                     if message[-x:] == password:
#                         break
#                     else:
#                         message += chr(int(hidden_bits[i], 2))
#                         hiddenmessage = message

#                 # Verifying the password
#                 if password in message:
#                     # Remove the password and decrypt the message
#                     decrypt = decrypt_rail_fence(hiddenmessage[:-x], 3)

#                     # ASCII Decryption
#                     decmsg = ""
#                     for ch in decrypt:
#                         asc = ord(ch) - 3  # Subtract 3 from the ASCII code to decrypt
#                         dech = chr(asc)
#                         decmsg += dech

#                     # Verify the password again
#                     if password in hiddenmessage:
#                         message = decmsg
#                     else:
#                         error_message = "You entered the wrong password. Please try again."
#                 else:
#                     error_message = "You entered the wrong password. Please try again."

#             except Exception as e:
#                 error_message = str(e)
#         else:
#             error_message = "Form is not valid. Please check your inputs."

#     else:
#         form = DecodeImageForm()

#     return render(request, 'base/decodeImg.html', {'form': form, 'message': message, 'error_message': error_message, 'steg_records': steg_records})


def decode_image(request):
    user = request.user
    steg_records = steganography.objects.filter(receiver=user).order_by('-created')
    message = ""
    error_message = ""

    if request.method == 'POST':
        password = request.POST.get('password')
        image_url = request.POST.get('image_url')

        # Remove the extra '/stegoImages/' if present
        image_url = image_url.replace('/stegoImages/stegoImages/', 'static/stegoImages/')

        try:
            image = File(open(image_url, 'rb'))
            img = Image.open(image)
            array = np.array(list(img.getdata()))

            if img.mode == 'RGB':
                n = 3
            elif img.mode == 'RGBA':
                n = 4

            total_pixels = array.size // n

            hidden_bits = ""
            for p in range(total_pixels):
                for q in range(0, 3):
                    hidden_bits += (bin(array[p][q])[2:][-1])

            hidden_bits = [hidden_bits[i:i+8] for i in range(0, len(hidden_bits), 8)]

            hiddenmessage = ""
            for i in range(len(hidden_bits)):
                x = len(password)
                if message[-x:] == password:
                    break
                else:
                    message += chr(int(hidden_bits[i], 2))
                    hiddenmessage = message

            # Verify the pass
            if password in message:
                # Remove the pass and decrypt the message
                decrypt = decrypt_rail_fence(hiddenmessage[:-x], 3)

                # ASCII Decryption
                decmsg = ""
                for ch in decrypt:
                    asc = ord(ch) - 3  # Subtract 3 from the ASCII code to decrypt
                    dech = chr(asc)
                    decmsg += dech

                # Verify the password again
                if password in hiddenmessage:
                    message = decmsg
                else:
                    error_message = "You entered the wrong password. Please try again."
            else:
                error_message = "You entered the wrong password. Please try again."

        except Exception as e:
            error_message = str(e)

        # if error occurs, return error msg and skip further processing - Corrected - 28th Oct
        if error_message:
            return render(request, 'base/decodeImg.html', {'error_message': error_message, 'steg_records': steg_records})

    return render(request, 'base/decodeImg.html', {'message': message, 'error_message': error_message, 'steg_records': steg_records})




# success view
def success(request):
    return render(request, 'base/success.html')

# try - login_register
def login_register(request):
    return render(request, 'base/login_register.html')

def userLanding(request):
    user = request.user
    sent_records = steganography.objects.filter(sender=user).order_by('-created')
    records_found_s = any(request.user == record.sender for record in sent_records)

    receiver_records = steganography.objects.filter(receiver=user).order_by('-created')
    records_found_r = any(request.user == record.receiver for record in receiver_records)
    
    for record in sent_records:
        record.image_name = record.image.url.split("/")[-1] 

    for record in receiver_records:
        record.image_name = record.image.url.split("/")[-1]
    return render(request, 'base/userLanding.html', {'sent_records': sent_records, 'receiver_records': receiver_records, 'records_found_r': records_found_r, 'records_found_s': records_found_s })

