import streamlit as st
from sqlalchemy import create_engine, Column, Integer, String, Date, Time, ForeignKey, Table, text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime, time

# Database setup
engine = create_engine('sqlite:///movie.db')
Session = sessionmaker(bind=engine)
session = Session()
Base = declarative_base()

# Many-to-Many Association Table: Movie and Room
movie_room_association = Table(
    'movie_room_association', Base.metadata,
    Column('movie_id', Integer, ForeignKey('Movies.movie_id'), primary_key=True),
    Column('room_id', Integer, ForeignKey('Rooms.room_id'), primary_key=True)
)

# Movie Model
class Movie(Base):
    __tablename__ = 'Movies'
    movie_id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    genre = Column(String(100))
    duration = Column(Integer)  # Duration in minutes
    release_date = Column(Date)
    rooms = relationship('Room', secondary=movie_room_association, back_populates='movies')

# Room Model
class Room(Base):
    __tablename__ = 'Rooms'
    room_id = Column(Integer, primary_key=True, autoincrement=True)
    room_number = Column(Integer, nullable=False)
    max_capacity = Column(Integer)
    movies = relationship('Movie', secondary=movie_room_association, back_populates='rooms')

# Showtime Model
class Showtime(Base):
    __tablename__ = 'Showtimes'
    showtime_id = Column(Integer, primary_key=True, autoincrement=True)
    movie_id = Column(Integer, ForeignKey('Movies.movie_id'), nullable=False)
    room_id = Column(Integer, ForeignKey('Rooms.room_id'), nullable=False)
    show_date = Column(Date, nullable=False)
    show_time = Column(Time, nullable=False)

# Create tables
Base.metadata.create_all(engine)

# Sample data using ORM
def add_sample_data():
    if not session.query(Room).first():
        session.add_all([
            Room(room_number=1, max_capacity=3),
            Room(room_number=2, max_capacity=2)
        ])
    if not session.query(Movie).first():
        movie1 = Movie(title="Inception", genre="Sci-Fi", duration=148, release_date=datetime(2010, 7, 16))
        movie2 = Movie(title="The Godfather", genre="Crime", duration=175, release_date=datetime(1972, 3, 24))
        movie1.rooms.append(session.query(Room).get(1))
        session.add_all([movie1, movie2])
    session.commit()

if st.button("Add Sample Data"):
    add_sample_data()

# ORM-based CRUD for Movies
def get_all_movies():
    return session.query(Movie).all()

def add_movie_orm(title, genre, duration, release_date):
    new_movie = Movie(title=title, genre=genre, duration=duration, release_date=release_date)
    session.add(new_movie)
    session.commit()
    return new_movie

def update_movie_orm(movie_id, title, genre, duration, release_date):
    movie = session.query(Movie).get(movie_id)
    movie.title = title
    movie.genre = genre
    movie.duration = duration
    movie.release_date = release_date
    session.commit()

def delete_movie_orm(movie_id):
    movie = session.query(Movie).get(movie_id)
    session.delete(movie)
    session.commit()

# Fetching movie-room associations with prepared statements
def fetch_movie_rooms(movie_id):
    query = text("""
        SELECT Rooms.room_id, Rooms.room_number
        FROM Rooms
        JOIN movie_room_association 
        ON Rooms.room_id = movie_room_association.room_id
        WHERE movie_room_association.movie_id = :movie_id
    """)
    result = session.execute(query, {'movie_id': movie_id}).fetchall()
    return [(row.room_id, row.room_number) for row in result]

# Updating movie-room associations with prepared statements
def update_movie_rooms(movie_id, room_ids):
    session.execute(text("DELETE FROM movie_room_association WHERE movie_id = :movie_id"), {'movie_id': movie_id})
    for room_id in room_ids:
        session.execute(
            text("INSERT INTO movie_room_association (movie_id, room_id) VALUES (:movie_id, :room_id)"),
            {'movie_id': movie_id, 'room_id': room_id}
        )
    session.commit()

# Generating a report with filters using prepared statements
def generate_report(start_date, end_date, room_id=None, movie_id=None):
    base_query = """
        SELECT Movies.title, Showtimes.show_date, Showtimes.show_time, Rooms.room_number, Movies.duration
        FROM Showtimes
        JOIN Movies ON Showtimes.movie_id = Movies.movie_id
        JOIN Rooms ON Showtimes.room_id = Rooms.room_id
        WHERE Showtimes.show_date BETWEEN :start_date AND :end_date
    """
    filters = {'start_date': start_date, 'end_date': end_date}
    if room_id:
        base_query += " AND Rooms.room_id = :room_id"
        filters['room_id'] = room_id
    if movie_id:
        base_query += " AND Movies.movie_id = :movie_id"
        filters['movie_id'] = movie_id

    result = session.execute(text(base_query), filters).fetchall()
    return result

# Streamlit App
st.title("Movie Theater Management System")

tab1, tab2, tab3 = st.tabs(["Manage Movies", "Add New Movie", "Generate Movie Report"])

with tab1:
    st.header("Manage Movies")
    movies = get_all_movies()
    movie_options = {movie.title: movie.movie_id for movie in movies}
    selected_movie_title = st.selectbox("Select a movie", options=movie_options.keys())

    if selected_movie_title:
        movie_id = movie_options[selected_movie_title]
        movie = session.query(Movie).get(movie_id)

        title = st.text_input("Title", value=movie.title)
        genre = st.text_input("Genre", value=movie.genre)
        duration = st.number_input("Duration (minutes)", value=movie.duration)
        release_date = st.date_input("Release Date", value=movie.release_date)

        associated_rooms = fetch_movie_rooms(movie_id)

        all_rooms = session.query(Room).all()
        selected_rooms = st.multiselect(
            "Select Rooms", 
            options=[(room.room_id, room.room_number) for room in all_rooms],
            default=associated_rooms,
            format_func=lambda x: f"Room {x[1]}"
        )
        room_ids = [room_id for room_id, _ in selected_rooms]

        if st.button("Update Movie"):
            update_movie_orm(movie_id, title, genre, duration, release_date)
            update_movie_rooms(movie_id, room_ids)
            st.success(f"Movie '{title}' updated successfully!")

        if st.button("Delete Movie"):
            delete_movie_orm(movie_id)
            st.success(f"Movie '{title}' deleted successfully!")

with tab2:
    st.header("Add a New Movie")
    new_title = st.text_input("New Movie Title")
    new_genre = st.text_input("New Movie Genre")
    new_duration = st.number_input("New Movie Duration (minutes)", min_value=0)
    new_release_date = st.date_input("New Movie Release Date")

    all_rooms = session.query(Room).all()
    selected_rooms = st.multiselect(
        "Select Rooms for New Movie", 
        options=[(room.room_id, room.room_number) for room in all_rooms],
        format_func=lambda x: f"Room {x[1]}"
    )
    room_ids = [room_id for room_id, _ in selected_rooms]

    if st.button("Add Movie"):
        new_movie = add_movie_orm(new_title, new_genre, new_duration, new_release_date)
        update_movie_rooms(new_movie.movie_id, room_ids)
        st.success(f"New movie '{new_title}' added successfully!")

with tab3:
    st.header("Generate Movie Report")
    rooms = session.query(Room).all()
    movies = session.query(Movie).all()

    selected_room = st.selectbox("Select Room (Optional)", options=[None] + [room.room_number for room in rooms])
    selected_movie = st.selectbox("Select Movie (Optional)", options=[None] + [movie.title for movie in movies])

    start_date = st.date_input("Start Date", value=datetime(2024, 1, 1))
    end_date = st.date_input("End Date", value=datetime(2024, 12, 31))

    if st.button("Generate Report"):
        room_id = next((room.room_id for room in rooms if room.room_number == selected_room), None)
        movie_id = next((movie.movie_id for movie in movies if movie.title == selected_movie), None)

        report = generate_report(start_date, end_date, room_id, movie_id)
        if report:
            for row in report:
                st.write(f"Movie: {row[0]}, Date: {row[1]}, Time: {row[2]}, Room: {row[3]}")
        else:
            st.write("No showtimes found.")