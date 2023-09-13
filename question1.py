from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import psycopg2
from motor.motor_asyncio import AsyncIOMotorClient
import uvicorn
from fastapi import File, UploadFile

app = FastAPI()

#Postgresql 
POSTGRESQL_DSN = "dbname=postgres user=postgres password=123456 host=localhost"
POSTGRESQL_CONNECTION = psycopg2.connect(POSTGRESQL_DSN)

#MongoDB 
MONGODB_URI = "mongodb://localhost:27017/MongDB"
MONGODB_CLIENT = AsyncIOMotorClient(MONGODB_URI)
MONGODB_DB = MONGODB_CLIENT["MongDB"]
MONGODB_COLLECTION = MONGODB_DB["profile_pictures"]


with POSTGRESQL_CONNECTION.cursor() as cursor:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id serial PRIMARY KEY,
            first_name VARCHAR(255),
            password VARCHAR(255),
            email VARCHAR(255) UNIQUE,
            phone VARCHAR(20)
        )
    """)
POSTGRESQL_CONNECTION.commit()


class UserRegister(BaseModel):
    first_name: str
    password: str
    email: str
    phone: str

class UserProfile(BaseModel):
    user_id: int
    full_name: str
    email: str
    phone: str

#functions that works for postgresql
def check_email_exist(email: str):
    with POSTGRESQL_CONNECTION.cursor() as cursor:
        cursor.execute("SELECT 1 FROM users WHERE email = %s", (email,))
        return cursor.fetchone() is not None

def register_user(user_data: UserRegister):
    with POSTGRESQL_CONNECTION.cursor() as cursor:
        cursor.execute(
            "INSERT INTO users (first_name, password, email, phone) VALUES (%s, %s, %s, %s) RETURNING user_id",
            (user_data.first_name, user_data.password, user_data.email, user_data.phone)
        )
        user_id = cursor.fetchone()[0]
        POSTGRESQL_CONNECTION.commit()
        return user_id

#MongoDB functions
async def save_profile_picture(user_id: int, profile_picture_content: bytes):
    await MONGODB_COLLECTION.insert_one({"user_id": user_id, "profile_picture": profile_picture_content})


async def get_profile_picture(user_id: int):
    document = await MONGODB_COLLECTION.find_one({"user_id": user_id})
    if document:
        return document["profile_picture"]
    return None

#endpoints
@app.post("/register/", response_model=UserProfile)
async def register_new_user(user_data: UserRegister):
    if check_email_exist(user_data.email):
        raise HTTPException(status_code=400, detail="Email already exists")
    
    user_id = register_user(user_data)
    return {"user_id": user_id, "full_name": user_data.first_name, "email": user_data.email, "phone": user_data.phone}

@app.post("/upload-profile-picture/{user_id}")
async def upload_profile_picture(user_id: int, profile_picture: UploadFile):
    try:
        profile_picture_content = await profile_picture.read()
        await save_profile_picture(user_id, profile_picture_content)
        return {"message": "Profile picture has been uploaded successfully !"}
    except Exception as e:
        return HTTPException(status_code=500, detail=f"Error while uploading the profile picture: {str(e)}")




@app.get("/user-details/{user_id}", response_model=UserProfile)
async def get_user_details(user_id: int):
    
    with POSTGRESQL_CONNECTION.cursor() as cursor:
        cursor.execute("SELECT user_id, first_name, email, phone FROM users WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()

    if result:
        user_id, first_name, email, phone = result
        profile_picture = await get_profile_picture(user_id)

        if profile_picture:
            return {"user_id": user_id, "full_name": first_name, "email": email, "phone": phone, "profile_picture": profile_picture}
        else:
            return {"user_id": user_id, "full_name": first_name, "email": email, "phone": phone, "profile_picture": None}
    
    raise HTTPException(status_code=404, detail="User not found")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
