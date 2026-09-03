from typing import List

from Objects.project import Project
import aiosqlite

class ProjectRepo:
    @staticmethod
    async def get_project_by_id(cursor,project_id) ->Project:
        select_statement = "SELECT * FROM projects WHERE id = ?"
        await cursor.execute(select_statement,(project_id,))
        row=await cursor.fetchone()
        return Project.from_row(row)


    @staticmethod
    async def get_all_projects(cursor) -> List[Project]:
        select_statement = "SELECT * FROM projects"
        await cursor.execute(select_statement)
        rows =await  cursor.fetchall()
        return [Project.from_row(row) for row in rows]


    @staticmethod
    async def insert_project(cursor,project_id, call_id, name=None, client=None) -> Project:
        insert_statement = "INSERT INTO projects (id, call_id, name, client) VALUES (?, ?, ?, ?)"
        await cursor.execute(insert_statement, (project_id, call_id, name, client))
        return Project(id=project_id, call_id=call_id,  name=name, client=client)

    # @staticmethod
    # def update_project(cursor, id, call_id, time_ending, name=None) -> ProjectDAO:
    #     update_statement = "UPDATE projects SET call_id = ?, time_ending = ?, name = ? WHERE id = ?"
    #     cursor.execute(update_statement, (call_id, time_ending, name, id))
    #     return ProjectDAO(id=id, call_id=call_id, time_ending=time_ending, name=name)

    @staticmethod
    async def delete_project(cursor, project_id):
        delete_statement = "DELETE FROM projects WHERE id = ?"
        await cursor.execute(delete_statement, (project_id,))