

### CREATE A REGIONAL CERTIFICATE
- It is really important to do this through the UI. The CLI will send you in endless circles. 
1. Go to **Certificates** in GCP
1. **Enable** the Cert Mgr API
1. When the Cert Manager UI appears, click **Create Certificate**
1. Name your cert **mtl-regional-cert**, choose **Regional** and set region to your service region (for me it's us-west1)
1. Choose a **Google-managed certificate**
1. Add the domain landing address you are using as the entry point for your load-balancer - for me its mtl.bintiholdings.com
1. Auth type is DNS Auth and VERY IMPORTANT - click** Create Missing DNS Authorization **before hitting the CREATE button. **Approve** in sidebar.
1. Click **Create** to Complete your Certificate. 
1. The row will show **Active** column with a green circle and checkmark when the DNS record is set up correctly.
1. Click back into the Certificate to get the info you need to create your second DNS record. 

## GO TO YOUR DOMAIN AND DNS MANAGER (for me it's Bluehost)
### CREATE A CNAME RECORD 
- projects/static-groove-476019-a5/locations/us-west1/dnsAuthorizations/dns-authz-mtl-bintiholdings-com
- DNS Record type: CNAME
- DNS Record name: _acme-challenge_fupu3vphu27nw5vk.mtl.bintiholdings.com.
- DNS Record data: 51d52b85-feca-441b-b2d9-ebb88ef9c692.2.us-west1.authorize.certificatemanager.goog.










## YOUR DOMAIN AND DNS MANAGER (for me it's Bluehost)
1. In the DNS provider, under the correct domain, I create an A record with:
   - Host: mts
   - Type: A
   - Value: 136.117.77.40 
   - TTL: 300
1. After propogation you can run:
    ```
         dig mtl.bintiholdings.com +short
    ```





## SECURING THE PROCESS
1. Once the above is working, test it by triggering it from moodle. You will need to go into the Moodle Site Admin Plugins page and find the Local section and click on **LinkedIn Share for Certificates** in the Gateway Endpoint field. put your SERVICE URL again (nothing added to the end) TODO - or do we add auth/linkedin/start (will depend on final solution.
1. Test the process end to end by triggering the share from the course banner share button. If it works, it's time to lock it down.
1. We have tried JWT tokens, and a gateway. Now we are trying restricted ingress. We'll have to see what happens. 
1. When everything is working and you don't want anyone hitting the service url directly you can run: 
```gcloud run services update mtl --region=us-west1 --no-default-url```
1. ```gcloud run services describe mtl --region=us-west1 \
  --format='value(metadata.annotations["run.googleapis.com/ingress-status"])'```
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
