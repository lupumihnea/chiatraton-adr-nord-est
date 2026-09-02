from typing import List

from DAO.projects_DAO import ProjectDAO


class ProjectRepository:
    @staticmethod
    def get_project_by_id(cursor,project_id) ->ProjectDAO:
        select_statement = "SELECT * FROM projects WHERE id = ?"
        cursor.execute(select_statement,(project_id,))
        row=cursor.fetchone()
        return ProjectDAO.from_row(row)


    @staticmethod
    def get_all_projects(cursor) -> List[ProjectDAO]:
        select_statement = "SELECT * FROM projects"
        cursor.execute(select_statement)
        rows = cursor.fetchall()
        return [ProjectDAO.from_row(row) for row in rows]


    @staticmethod
    def insert_project(cursor,project_id, call_id, name=None) -> ProjectDAO:
        insert_statement = "INSERT INTO projects (id, call_id, name) VALUES (?, ?, ?)"
        cursor.execute(insert_statement, (project_id, call_id, name))
        return ProjectDAO(id=project_id, call_id=call_id,  name=name)

    # @staticmethod
    # def update_project(cursor, id, call_id, time_ending, name=None) -> ProjectDAO:
    #     update_statement = "UPDATE projects SET call_id = ?, time_ending = ?, name = ? WHERE id = ?"
    #     cursor.execute(update_statement, (call_id, time_ending, name, id))
    #     return ProjectDAO(id=id, call_id=call_id, time_ending=time_ending, name=name)

    @staticmethod
    def delete_project(cursor, project_id):
        delete_statement = "DELETE FROM projects WHERE id = ?"
        cursor.execute(delete_statement, (project_id,))