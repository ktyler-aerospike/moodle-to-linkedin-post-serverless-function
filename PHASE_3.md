### ADD A SECOND FRONTEND IN YOUR LOAD BALANCER
1. Drill in to the load balancer you created. 
1. Choose **Edit**.
2. **Frontend Configuration**
1. Sidebar: **Add Frontend IP and port**.
1. Name your second front end similar to the first but use an S on the end of HTTP. https
1. Choose the **HTTPS** protocol
2. **Standard**
1. Leave Port **443**
2. Choose the IP address you already created and tested for your load balancer. Both frontends will use the same IP. One will use port 80 and the other will use 443. One will have an SSL certificate with it and the other will not.
3. Choose **Certificates**.
4. **Add Certificate**.
   1. **Create a New Certificate**.
   7. **Google Managed**
   1.** Public**
   2. Domain Names: Put in the address you plan to use something like **badge-share.mysite.com** (but with your domain instead of mysite)
   3. **DNS Authorization**
   4. Create the DNS Authorization by clicking the blue button. I might appear as if you haven't clicked it, but be patient. DNS Auth info will appear. 
9. Copy and past the DNS Auth info somewhere. 

## GO TO YOUR DOMAIN AND DNS MANAGER (for me it's Bluehost)
### CREATE AN A NAME RECORD
1. In the DNS provider, under the correct domain, I create an A record with:
   - Host: badge-share
   - Type: A
   - Value: (the IP you've been using in your frontend records) 
   - TTL: 300

### CREATE A CNAME RECORD 
- DNS Record type: CNAME
- DNS Record name (Host): _acme-challenge_fupu3vphu27nw5vk.badge-share.mysite.com.
- DNS Record data (Value): 51d52b85-feca-441b-b2d9-ebb88ef9c692.2.us-west1.authorize.certificatemanager.goog.

- My A name record was almost instant. I could go to dnschecker.org, look up my A name and it showed my IP. 
- My CNAME record took 45 minutes to an hour to show up.
- Once both of them show up you should be able to go to GCP Certificate Manger and see the status as Active.
- Once status is active you should be able to use http://badge-share.mysite.com and https://badge-share.mysite.com.
- HTTP will still say Not Secure but HTTPS is secure now because you have the Certificate in place.


## SECURING THE PROCESS
1. Once the above is working, test it by triggering it from moodle. You will need to go into the Moodle Site Admin Plugins page and find the Local section and click on **LinkedIn Share for Certificates** in the Gateway Endpoint field. put your SERVICE URL again (nothing added to the end) (no /auth/linkedin/start bc that gets added by the plugin code).
1. Test the process end to end by triggering the share from the course banner share button. If it works
1. When everything is working and you don't want anyone hitting the service url directly you can run: 
```gcloud run services update mtl --region=us-west1 --no-default-url```
1. ```gcloud run services describe mtl --region=us-west1 \
  --format='value(metadata.annotations["run.googleapis.com/ingress-status"])'```



## THIS IS ALL REALLY IFFY - I don't think it works and I'm not certain it's needed. 

# expected: internal-and-cloud-load-balancing
1. 

### Update the INGRESS SETTINGS
-- this may not even be needed
1. You have to use gcloud for this unfortunately.
    ```
   gcloud auth login
    ```
1. Run this command to set 3 variables: 
    ```PROJECT_ID = 'static-groove-476019-a5'
       REGION="us-west1"
       SERVICE="mtl"
    ```
1. Set your project as context for future commands:
     ```
   gcloud config set project $PROJECT_ID
     ```
   
1. **SET THE INGRESS POLICY:**
   ```
   gcloud run services update $SERVICE \
     --region=$REGION \
     --ingress=internal-and-cloud-load-balancing
   ```
1. **CHECK THAT THE INGRESS POLICY IS IN EFFECT** 
   ```
   gcloud run services describe $SERVICE --region=$REGION \
   --format='table(
    metadata.annotations["run.googleapis.com/ingress-status"],
    spec.template.metadata.annotations["run.googleapis.com/ingress"]
   )'
   ```
1. **YOU CAN ALSO CHECK THEM BY NAME**
   ```
    gcloud run services describe $SERVICE --region=$REGION \
      --format='value(spec.template.metadata.annotations["run.googleapis.com/ingress"])'
   ```
