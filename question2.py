from fastapi import FastAPI, HTTPException, Query, File, UploadFile, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import psycopg2
from pathlib import Path
import os


app = FastAPI()


db_config = {
    'dbname': 'postgres',
    'user': 'postgres',
    'password': '123456',
    'host': 'localhost',
}


class UserRegistration(BaseModel):
    full_name: str = Form(..., title="Full Name")
    email: str = Form(..., title="Email")
    password: str = Form(..., title="Password")
    phone: str = Form(..., title="Phone")
    profile_picture: UploadFile = File(..., title="Profile Picture")


class UserDetails(BaseModel):
    user_id: int
    full_name: str
    email: str
    phone: str
    profile_picture: str


def connect_to_db():
    conn = psycopg2.connect(**db_config)
    return conn


def create_users_table():
    conn = connect_to_db()
    cursor = conn.cursor()
    create_table_query = """
    CREATE TABLE IF NOT EXISTS Users (
        user_id SERIAL PRIMARY KEY,
        full_name VARCHAR(100) NOT NULL,
        email VARCHAR(100) UNIQUE NOT NULL,
        password VARCHAR(100) NOT NULL,
        phone VARCHAR(15) UNIQUE NOT NULL
    )
    """
    cursor.execute(create_table_query)
    conn.commit()
    conn.close()


def create_profile_table():
    conn = connect_to_db()
    cursor = conn.cursor()
    create_table_query = """
    CREATE TABLE IF NOT EXISTS Profile (
        user_id SERIAL PRIMARY KEY,
        profile_picture VARCHAR(255) NOT NULL
    )
    """
    cursor.execute(create_table_query)
    conn.commit()
    conn.close()


@app.post("/register", response_model=UserDetails)
async def register_user(user_data: UserRegistration):
    create_users_table()
    create_profile_table()
    
    #this part checks  if the email or phone number already exist in the db
    conn = connect_to_db()
    cursor = conn.cursor()
    check_query = """
    SELECT * FROM Users WHERE email = %s OR phone = %s
    """
    cursor.execute(check_query, (user_data.email, user_data.phone))
    existing_user = cursor.fetchone()
    
    if existing_user:
        conn.close()
        raise HTTPException(status_code=400, detail="Email or phone already exists")

    #inserting to the users table
    insert_query = """
    INSERT INTO Users (full_name, email, password, phone) VALUES (%s, %s, %s, %s) RETURNING user_id
    """
    cursor.execute(insert_query, (user_data.full_name, user_data.email, user_data.password, user_data.phone))
    user_id = cursor.fetchone()[0]

    #Save profile picture to Profile table
    profile_picture_path = f"uploads/{user_id}_{user_data.profile_picture.filename}"
    profile_picture_path = profile_picture_path.replace(" ", "_")
    profile_picture_path = profile_picture_path.lower()

    cursor.execute("INSERT INTO Profile (user_id, profile_picture) VALUES (%s, %s)",
                   (user_id, profile_picture_path))
    conn.commit()

    
    upload_folder = Path("uploads")
    upload_folder.mkdir(parents=True, exist_ok=True)
    profile_picture_path = upload_folder / profile_picture_path
    with profile_picture_path.open("wb") as profile_picture_file:
        profile_picture_file.write(user_data.profile_picture.file.read())

    conn.close()
    return UserDetails(user_id=user_id, full_name=user_data.full_name, email=user_data.email,
                       phone=user_data.phone, profile_picture=profile_picture_path)


@app.get("/user/{user_id}", response_model=UserDetails)
async def get_user_details(user_id: int):
    conn = connect_to_db()
    cursor = conn.cursor()

    query = """
    SELECT U.user_id, U.full_name, U.email, U.phone, P.profile_picture
    FROM Users U
    INNER JOIN Profile P ON U.user_id = P.user_id
    WHERE U.user_id = %s
    """
    cursor.execute(query, (user_id,))
    user_data = cursor.fetchone()

    conn.close()

    if user_data:
        return UserDetails(user_id=user_data[0], full_name=user_data[1], email=user_data[2],
                           phone=user_data[3], profile_picture=user_data[4])
    else:
        raise HTTPException(status_code=404, detail="User not found")
