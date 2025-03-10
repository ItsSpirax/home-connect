import pandas as pd
import ast
import faiss
import numpy as np
import sqlite3
from sklearn.feature_extraction.text import TfidfVectorizer
import google.generativeai as genai
import re
from dotenv import load_dotenv
import os

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.0-flash-lite-001")


def preprocess_data(df):
    """Preprocesses the property data by converting amenities to lists and standardizing location format."""
    df["amenities"] = df["amenities"].apply(
        lambda x: ast.literal_eval(x) if isinstance(x, str) else x
    )
    df["location"] = df["location"].str.lower()
    df["amenities"] = df["amenities"].apply(
        lambda x: ",".join(x) if isinstance(x, list) else x
    )
    return df


def save_cleaned_data(csv_path, db_path="data/property_data.db"):
    """Loads raw CSV, preprocesses data, and stores it in SQLite."""
    raw_df = pd.read_csv(csv_path)
    df_cleaned = preprocess_data(raw_df)
    conn = sqlite3.connect(db_path)
    df_cleaned.to_sql("properties", conn, if_exists="replace", index=False)
    conn.close()
    print("Data cleaned and saved successfully!")


def load_cleaned_data(db_path="data/property_data.db"):
    """Loads cleaned property data from SQLite."""
    conn = sqlite3.connect(db_path)
    df = pd.read_sql("SELECT * FROM properties", conn)
    conn.close()
    df["amenities"] = df["amenities"].apply(
        lambda x: x.split(",") if isinstance(x, str) else x
    )
    return df


def get_user_input():
    """Gets user input for property search criteria."""
    user_size = int(input("Enter preferred size (e.g., 2 for 2BHK): "))
    user_price = float(input("Enter maximum budget: "))
    user_location = input("Enter preferred location: ")
    user_amenities = input("Enter preferred amenities (comma-separated): ").split(",")
    print(user_amenities)
    return user_size, user_price, user_location, user_amenities


def find_similar_properties(df, user_size, user_price, user_location, user_amenities):
    """Finds the top 5 non-duplicate properties based on size, location, price, and amenities."""
    df_filtered = df[df["size"] == user_size].copy()
    if df_filtered.empty:
        return "No properties found with the given size."

    exact_match = df_filtered[df_filtered["location"] == user_location.lower()]
    partial_match = df_filtered[
        df_filtered["location"].str.contains(user_location.lower(), na=False)
    ]
    df_filtered = pd.concat([exact_match, partial_match]).drop_duplicates(
        subset=["link"], keep="first"
    )
    if df_filtered.empty:
        return "No properties found in the specified location."

    upper_price_limit = user_price * 1.05
    df_filtered = df_filtered[df_filtered["price"] <= upper_price_limit]
    if df_filtered.empty:
        return "No properties found within the price range."

    df_filtered["amenities_str"] = df_filtered["amenities"].apply(lambda x: " ".join(x))
    user_amenities_str = " ".join(user_amenities)

    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(
        df_filtered["amenities_str"].tolist() + [user_amenities_str]
    )
    embeddings = tfidf_matrix[:-1].toarray().astype("float32")
    user_embedding = tfidf_matrix[-1].toarray().astype("float32")

    d = embeddings.shape[1]
    index = faiss.IndexFlatL2(d)
    index.add(embeddings)
    _, indices = index.search(user_embedding, 10)

    top_results = df_filtered.iloc[indices[0]].drop_duplicates(subset=["link"]).head(5)
    return top_results[
        [
            "link",
            "size",
            "price",
            "location",
            "amenities",
            "description",
            "building_name",
        ]
    ]


def extract_keywords_from_text(user_text):
    """
    Extracts size, price, location, and amenities from a given text using Google Gemini.
    Returns structured data.
    """
    prompt = f"""
    Extract the following details from the given text and return them in JSON format in ENGLISH ONLY DONT KEEP ANY LOCAL LANGUAGE IN OUTPUT:
    - **Size**: The apartment size in numeric format. Eg, For 1BHK give output as 1. 
    - **Price**: The budget mentioned (assumed in INR unless stated otherwise).
    - **Location**: The place where the user is looking for the apartment.
    - **Amenities**: Any specific features the user is asking for.

    Example Format:
    {{
        "size": "2BHK",
        "price": 50000,
        "location": "Mumbai",
        "amenities": ["gym", "swimming pool"]
    }}

    Text: "{user_text}"
    """
    response = model.generate_content(prompt)

    # Extract JSON output using regex to handle inconsistencies
    match = re.search(r"\{.*\}", response.text, re.DOTALL)
    if match:
        extracted_data = eval(match.group())  # Convert JSON string to dict
    else:
        extracted_data = {
            "size": None,
            "price": None,
            "location": None,
            "amenities": [],
        }

    return extracted_data


if __name__ == "__main__":
    db_path = "data/property_data.db"
    df = load_cleaned_data(db_path)

    user_query = "Looking for a 2BHK in Vikhroli within 1,20,000 budget."
    result = extract_keywords_from_text(user_query)

    top_properties = find_similar_properties(
        df, result["size"], result["price"], result["location"], result["amenities"]
    )
    print(top_properties)
