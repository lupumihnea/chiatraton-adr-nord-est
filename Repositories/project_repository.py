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