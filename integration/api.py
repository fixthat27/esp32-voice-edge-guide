import os, secrets
from typing import Literal
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from integration.service import CommandService, Rejected, Conflict
class Command(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:str=Field(min_length=8,max_length=128,pattern=r'^[A-Za-z0-9_-]+$')
    source:Literal['esp32_tinyml']
    device_id:str=Field(max_length=64)
    intent:Literal['device_control']
    action:Literal['turn_on','turn_off']
    value:StrictBool
    confidence:float=Field(ge=0,le=1,allow_inf_nan=False)
    model_version:str=Field(min_length=1,max_length=64)
app=FastAPI(title='Voice command shadow reference')
service=CommandService(os.getenv('VOICE_DB','commands.sqlite3'))
@app.post('/api/v1/commands')
def command(body:Command,x_api_key:str=Header(default='')):
    token=os.getenv('VOICE_API_KEY','')
    if not token: raise HTTPException(503,'Configure VOICE_API_KEY')
    if not secrets.compare_digest(x_api_key,token): raise HTTPException(401,'Invalid API key')
    try: return service.execute(body.model_dump())
    except Rejected as e: raise HTTPException(422,str(e)) from e
    except Conflict as e: raise HTTPException(409,str(e)) from e
