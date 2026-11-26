'use strict';
const {randomBytes,createCipheriv}=require('node:crypto');
const fs=require('node:fs');
const key=randomBytes(32), iv=randomBytes(12);
const cipher=createCipheriv('aes-256-gcm',key,iv);
const data=Buffer.concat([cipher.update(fs.readFileSync(0)),cipher.final(),cipher.getAuthTag()]);
process.stdout.write(JSON.stringify({key:key.toString('base64url'),iv:iv.toString('base64'),data:data.toString('base64')}));
