import tests.tests
from dome.auxiliary.entity import Entity
import sqlite3
import pandas as pd

from dome.config import LIMIT_REGISTERS
from util import date_util


class DomainEngine:
    def __init__(self, AC):
        self.__AC = AC  # Autonomous Controller Object
        self.__TDB = None  # Transaction Database Connection
        self.__entities_map = {}  # map of entities
        self.init_entities()

    def init_entities(self):
        # update current entities and attributes
        self.__entities_map.clear()
        sql_cmd = "SELECT name FROM sqlite_master WHERE type ='table' AND name LIKE '" + self.__getEntityDBNamePrefix() + "%';"
        query = self.__executeSqlCmd(sql_cmd)
        for row in query.fetchall():
            entity_name = row[0].replace(self.__getEntityDBNamePrefix(), '')
            entity_obj = self.saveEntity(entity_name)
            # getting attributes
            sql_cmd = "SELECT name, type FROM PRAGMA_TABLE_INFO('" + row[0] + "') where name<>'id' and " \
                                                                        "name<>'dome_created_at' and " \
                                                                        "name<>'dome_updated_at';"
            query2 = self.__executeSqlCmd(sql_cmd)
            for column in query2.fetchall(): # column has the name and type of attribute
                entity_obj.addAttribute(column[0], column[1], False)  # TODO: manage type and notnull

    def saveEntity(self, entity_name):
        # TODO: update meta data (MDB) and Transaction Data (TDB)
        # if entity already exists, return the object from map
        if self.entityExists(entity_name):
            return self.__entities_map.get(entity_name)
        # else
        # create new entity
        e = Entity(entity_name.title())
        # add entity in map
        self.__entities_map[entity_name] = e
        # return entity
        return e

    def getEntities(self):
        return list(self.__entities_map.values())

    def get_entities_map(self):
        return self.__entities_map

    def addAttribute(self, entity, name, type, notnull=False):
        # TODO: #2 update meta data (MDB) and Transaction Data (TDB)
        # ...
        entity.addAttribute(name, type, notnull)
        return True

    def entityExists(self, entity_name):
        return entity_name in self.__entities_map.keys()

    def __executeSqlCmd(self, sqlCmd, params=()):
        if self.__TDB is None:
            self.__TDB = sqlite3.connect(self.__AC.getTransactionDB_path(), check_same_thread=False)
        result = self.__TDB.cursor().execute(sqlCmd, params)
        self.__TDB.commit()

        return result

    def __getEntityDBName(self, entity_name):
        return self.__getEntityDBNamePrefix() + entity_name

    def __getEntityDBNamePrefix(self):
        return self.__AC.getWebApp_path() + '_'

    def add(self, entity, attributes):
        sql_cmd = "INSERT OR REPLACE INTO " + self.__getEntityDBName(entity)
        sql_cmd += "(dome_created_at, dome_updated_at, "
        for k in attributes.keys():
            if(self.entityExists(k)):
                sql_cmd += k + "_id, "
            else:
                sql_cmd += k + ", "
        sql_cmd = sql_cmd[:-2]  # removing the last comma
        sql_cmd += ") values((datetime('now', 'localtime')), (datetime('now', 'localtime')), "
        
        for k, v in attributes.items():
            if self.entityExists(k):
               sql_cmd2 = "SELECT id FROM " + self.__getEntityDBName(k) + " WHERE name = ?"
               params = (str(v),)
               query = self.__executeSqlCmd(sql_cmd2, params)

               row = query.fetchone()

               if row is not None:
                    id = row[0]
                    att_val = str(id)
               else:
                    att_val = str(v) # doesn't exists this value in the table
        
            else:
                att_val = str(v)
                
            att_val = att_val.replace("'", "") # removing ' from the string to prevent syntax errors
            sql_cmd += "'" + att_val + "', "

        sql_cmd = sql_cmd[:-2]  # removing the last comma
        sql_cmd += ")"
        self.__executeSqlCmd(sql_cmd)

    def update(self, entity, attributes, where_clause):
        sql_cmd = "UPDATE " + self.__getEntityDBName(entity) + " SET"
        sql_cmd += " dome_updated_at = (datetime('now', 'localtime')),"

        for attribute_name, attribute_value in attributes.items():
            # removing ' from the attribute_value to prevent syntax errors
            attribute_value = attribute_value.replace("'", "")

            if self.entityExists(attribute_name):
                sql_cmd2 = "SELECT id FROM " + self.__getEntityDBName(attribute_name) + " WHERE name = ?"
                params = (str(attribute_value),)
                query = self.__executeSqlCmd(sql_cmd2, params)

                row = query.fetchone()

                if row is not None:
                     id = row[0]
                     att_val = str(id)
                else: # doesn't exists this value in the table
                     att_val = str(attribute_value)

                att_val = att_val.replace("'", "")
                sql_cmd += ' ' + attribute_name + "='" + att_val + "',"

            else:
                sql_cmd += ' ' + attribute_name + "='" + attribute_value + "',"
        
        sql_cmd = sql_cmd[:-1]  # removing the last comma
        # fill-up the where clause
        if where_clause:
            sql_cmd += " where "
            for k in where_clause.keys():
                if k == 'id':
                    sql_cmd += " id=" + where_clause[k] + " AND "
                else:
                    sql_cmd += "LOWER(" + k + ") = LOWER('" + where_clause[k] + "') AND "
            sql_cmd = sql_cmd[:-4]  # removing the last AND
        return self.__executeSqlCmd(sql_cmd)

    def read(self, entity, attributes):
        if not self.entityExists(entity):
            return None
        # else: entity exists
        entity_obj = self.__entities_map[entity]
        sql_cmd = "SELECT * FROM " + self.__getEntityDBName(entity) + " where (1=1)"
        for k in attributes.keys():
            if k == 'id':
                sql_cmd += " AND id=" + attributes[k]
            # checking if the attribute exists for the current entity
            elif k in entity_obj.getAttributes():
                sql_cmd += " AND LOWER(" + k + ") LIKE LOWER('%" + attributes[k] + "%')"
            elif k == entity:
                sql_cmd += " AND ("
                for attribute in entity_obj.getAttributes():
                    sql_cmd += attribute.name + " = '" + attributes[k] + "' OR "
                sql_cmd = sql_cmd[:-4]
                sql_cmd += ")"
            elif k == 'dome_created_at':
                attributes[k] = date_util.format(attributes[k])
                sql_cmd += " AND DATE(dome_created_at) = " + attributes[k]
            elif k == 'last_clause':
                # ordering by the newest
                # dome_updated_at is a reserved field automatically updated by the system
                sql_cmd += " ORDER BY dome_updated_at DESC"
                # put limit to LIMIT_REGISTERS
                sql_cmd += " LIMIT " + str(1)
                query = self.__executeSqlCmd(sql_cmd)
                cols = [column[0] for column in query.description]
                data = query.fetchall()
                if len(data) == 0:
                    return None
                # else
                results = pd.DataFrame.from_records(data=data, columns=cols, index=['id'])
                results.drop(['dome_created_at', 'dome_updated_at'], axis=1, inplace=True)
                return results
            else:
                return None  # there is no that attribute in entity

        # ordering by the newest
        # dome_updated_at is a reserved field automatically updated by the system
        sql_cmd += " ORDER BY dome_updated_at DESC"
        # put limit to LIMIT_REGISTERS
        sql_cmd += " LIMIT " + str(LIMIT_REGISTERS)
        query = self.__executeSqlCmd(sql_cmd)
        cols = [column[0] for column in query.description]
        data = query.fetchall()
        if len(data) == 0:
            return None
        # else
        results = pd.DataFrame.from_records(data=data, columns=cols, index=['id'])
        results.drop(['dome_created_at', 'dome_updated_at'], axis=1, inplace=True)
        return results

    def delete(self, entity, attributes):
        sql_cmd = "DELETE FROM " + self.__getEntityDBName(entity) + " where "
        for k in attributes.keys():
            sql_cmd += "LOWER(" + k + ") = LOWER('" + attributes[k] + "') AND "
        sql_cmd = sql_cmd[:-4]  # removing the last AND
        return self.__executeSqlCmd(sql_cmd)
