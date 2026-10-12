
import time

import streamlit as st
from google import genai
from PIL import Image
from twilio.rest import Client

from prompts import (
    SYSTEM_PROMPT,
    WELCOME_MESSAGE_TEMPLATE,
    SUMMARY_REQUEST_PROMPT,
)


# ----------------------------------
# 1. Load API credentials
# ----------------------------------

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
TWILIO_ACCOUNT_SID = st.secrets["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = st.secrets["TWILIO_AUTH_TOKEN"]


# ----------------------------------
# 2. Create and reuse API clients
# ----------------------------------

@st.cache_resource
def get_gemini_client():
    return genai.Client(api_key=GEMINI_API_KEY)


@st.cache_resource
def get_twilio_client():
    return Client(
        TWILIO_ACCOUNT_SID,
        TWILIO_AUTH_TOKEN,
    )


gemini_client = get_gemini_client()
twilio_client = get_twilio_client()


# ----------------------------------
# 3. Page setup
# ----------------------------------

st.title("🥗 MacroSnap")
st.caption("Your friendly AI nutrition buddy")


# ----------------------------------
# 4. Ask for the user's name
# ----------------------------------

if "user_name" not in st.session_state:
    st.session_state.user_name = ""

if not st.session_state.user_name:
    name = st.text_input("What should I call you?")

    if st.button("Get started") and name.strip():
        st.session_state.user_name = name.strip()
        st.rerun()


# ----------------------------------
# 5. Chat interface
# ----------------------------------

if st.session_state.user_name:

    st.write(
        WELCOME_MESSAGE_TEMPLATE.format(
            name=st.session_state.user_name
        )
    )

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display previous messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # Text input
    user_input = st.chat_input(
        "Describe what you ate..."
    )

    # Image upload
    uploaded_image = st.file_uploader(
        "Or upload a photo of your meal 📸",
        type=["jpg", "jpeg", "png"],
        key="meal_image",
    )

    analyze_photo = st.button("Analyze photo 📸")

    # Process a text message or an explicitly submitted photo
    if user_input or (uploaded_image and analyze_photo):

        user_message = (
            user_input
            or "Please analyze this meal photo. "
            "Estimate calories, protein, carbs, and fat."
        )

        # Build the request using previous conversation history
        contents = [
            SYSTEM_PROMPT,
            *[
                f'{m["role"]}: {m["content"]}'
                for m in st.session_state.messages
            ],
            f"user: {user_message}",
        ]

        # Attach the image when available
        if uploaded_image:
            image = Image.open(uploaded_image)
            contents.append(image)

        # Save and display the user's message
        st.session_state.messages.append(
            {
                "role": "user",
                "content": user_message,
            }
        )

        with st.chat_message("user"):
            st.write(user_message)

            if uploaded_image:
                st.image(
                    uploaded_image,
                    caption="Your meal",
                )

        # Generate Gemini's response
        with st.chat_message("assistant"):
            with st.spinner("Analyzing your meal..."):
                try:
                    response = None

                    # Retry temporary server errors
                    for attempt in range(3):
                        try:
                            response = (
                                gemini_client.models.generate_content(
                                    model="gemini-3.5-flash",
                                    contents=contents,
                                )
                            )
                            break

                        except Exception as e:
                            error_message = str(e)

                            is_temporary_error = (
                                "503" in error_message
                                or "UNAVAILABLE" in error_message
                            )

                            if (
                                is_temporary_error
                                and attempt < 2
                            ):
                                time.sleep(
                                    2 * (attempt + 1)
                                )
                            else:
                                raise

                    answer = (
                        response.text
                        or "Sorry, I couldn't generate a response. "
                        "Please try again."
                    )

                except Exception as e:
                    error_message = str(e)

                    if (
                        "503" in error_message
                        or "UNAVAILABLE" in error_message
                    ):
                        answer = (
                            "Gemini is busy right now. "
                            "Please try again in a little while. 🥗"
                        )
                    else:
                        answer = (
                            "Sorry, something went wrong. "
                            "Please check your connection and try again."
                        )

                st.write(answer)

        # Save Gemini's response
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": answer,
            }
        )


# ----------------------------------
# 6. WhatsApp summary interface
# ----------------------------------


# ----------------------------------
# 6. WhatsApp summary and sending
# ----------------------------------


# ----------------------------------
# 6. WhatsApp summary and sending
# ----------------------------------

if st.session_state.user_name:

    st.divider()
    st.subheader("📱 Send your meal summary to WhatsApp")

    phone_number = st.text_input(
        "Your WhatsApp number",
        placeholder="+91XXXXXXXXXX",
        help="Enter your number with the country code.",
        key="whatsapp_phone",
    )

    if st.button("Send details to WhatsApp"):

        if not phone_number.strip():
            st.warning("Please enter your WhatsApp number.")

        elif not st.session_state.get("messages"):
            st.warning("Please analyze a meal before requesting a summary.")

        else:
            try:
                with st.spinner("Preparing your meal summary..."):

                    # Collect the conversation
                    conversation = "\n".join(
                        f'{m["role"]}: {m["content"]}'
                        for m in st.session_state.messages
                    )

                    # Ask Gemini to summarize, retrying temporary errors
                    summary_response = None

                    for attempt in range(3):
                        try:
                            summary_response = (
                                gemini_client.models.generate_content(
                                    model="gemini-3.5-flash",
                                    contents=[
                                        SUMMARY_REQUEST_PROMPT,
                                        conversation,
                                    ],
                                )
                            )
                            break

                        except Exception as e:
                            error_message = str(e)

                            is_temporary_error = (
                                "503" in error_message
                                or "UNAVAILABLE" in error_message
                            )

                            if is_temporary_error and attempt < 2:
                                time.sleep(2 * (attempt + 1))
                            else:
                                raise

                    summary = (
                        summary_response.text
                        if summary_response
                        else None
                    )

                    if not summary:
                        st.error("Could not create a meal summary.")
                        st.stop()

                    # Send the summary using the connected WhatsApp Sandbox
                    message = twilio_client.messages.create(
                        from_="whatsapp:+14155238886",
                        to=f"whatsapp:{phone_number.strip()}",
                        body=summary,
                    )

                st.success("WhatsApp message submitted successfully! 🎉")
                st.write("Message status:", message.status)

            except Exception as e:
                error_message = str(e)

                if (
                    "503" in error_message
                    or "UNAVAILABLE" in error_message
                ):
                    st.error(
                        "Gemini is busy right now. "
                        "Please wait a little and try again."
                    )
                else:
                    st.error("Could not send the WhatsApp message.")
                    st.caption(f"Error details: {error_message}")