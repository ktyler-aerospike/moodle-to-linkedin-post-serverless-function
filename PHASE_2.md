# SECURE ACCESS TO THE SERVICE

### Create the VPC Network with Subnet
1. Go to VPC (use the GCP search bar at the top of the console)
2. Select + Create a VPC network
3. Name it mtl-lb-network
4. Choose your region (ours is us-west1)
5. Custom
1. DO NOT CREATE A SUBNET YET
2. DO NOT SELECT a FIREWALL RULE YET
3. Disabled
7. Regional
8. Legacy
9. DO NOT USE DNS CONFIG
10. When VPC is created, reenter and choose the SUBNETS TAB:
    1. Choose + Add subnet
    1. mtl-lb-network-subnet
    1. Choose your region.
    1. Choose Regional Managed Proxy
    1. Choose Active
    1. Leave box unchecked I guess?
    1. Paste 10.129.0.0/23 into IPv4 Range
    1. Click Add
    1. Your subnet should appear under Reserved proxy-only subnets for load balancing
   
## RESERVE A REGIONAL IP - I THINK THIS IS A MISTAKE AND YOU SHOULD NOT CREATE THIS OR THE A NAME RECORD IN ADVANCE
1. While still in the VPC Nework Area of GCP
2. Click IP Addresses in the sidebar.
3. Click Reserve External
4. Choose Standard
5. IPv4
6. Regional
7. Select Region
8. We can't attach it to a load balancer quite yet, but we will do that later.

- I think it's better to create it during the front end config for the load balancer



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

## RESERVE A REGIONAL IP FOR THE SAME ADDRESS




## LOAD BALANCER
- The kind of Load Balancer we are creating is called a url-map behind the scenes.
- Our LB will be called mtl-load-balancer
- Our LB will need a VPC network with a subnet so we'll create that first.


- NEG - Network Endpoint Group
- Name your NEG the same as your service plus a dash and neg.

1. **SET MORE SESSION VARIABLES**
    ```
    NEG_NAME=${SERVICE}-"neg" 
    BACKEND=${SERVICE}-backend
    ```

1. **Create your Network Endpoint Group - It's a simple neg that points at your Cloud Run Project**
    ```
    gcloud compute network-endpoint-groups create $NEG_NAME \
      --region=$REGION \
      --network-endpoint-type=serverless \
      --cloud-run-service=$SERVICE
    ```

1. If asked, choose to **enable compute.googleapis.com**

1. **Create Your Backend Service Of the Load Balancer - in our case it forwards from Moodle out to our Cloud Run**
    ```
    gcloud compute backend-services create $BACKEND \
      --load-balancing-scheme=EXTERNAL_MANAGED \
      --protocol=HTTP \
      --region=$REGION
    ```

1. **Connect Your NEG to your Backend Service**
    ```
    gcloud compute backend-services add-backend $BACKEND \
      --region=$REGION \
      --network-endpoint-group=$NEG_NAME \
      --network-endpoint-group-region=$REGION
    ```

## Set up the DNS Record -- This is part of setting up the FrontEnd of the Load Balancer 
1. **Create an IP Variable**
    ```
    IP_NAME=mtl-ip
    ```
1. **Reserve an external regional IP**
    ```
    gcloud compute addresses create $IP_NAME --region=$REGION
    ```
1. **Read it back**
    ```
    gcloud compute addresses describe $IP_NAME \
      --region=$REGION --format="get(address)"
    ```

1. **Assign your reserved IP to a new variable**
    ```
    IP_ADDR=$(gcloud compute addresses describe $IP_NAME --region=$REGION --format='value(address)')
    ```
- Mine is 136.117.77.40

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

## BACK TO GOOGLE CLOUD


## BACK TO GOOGLE CLOUD
### CREATE Load Balancer, THE VPC/SUBNET, THE HTTPS PROXY, THE CERT and a FORWARDING RULE
    ```
    HOST=${SERVICE}-bintiholdings.com
    URLMAP=${SERVICE}-load-balancer
    ```

### This should really be called the Load Balancer but it's called a url-map
1. CREATE THE URL MAP:
    ```
    gcloud compute url-maps create $URLMAP \
      --default-service=$BACKEND \
      --region=$REGION
    ```
1. Check the map's details:
    ```  
    gcloud compute url-maps describe mtl-urlmap --region=$REGION
    ```

### CREATE VPC & SUBNET
1. Create Some Variables
    ```
    LB_NAME=mtl-lb
    NETWORK=mtl-lb-network
    TARGET_PROXY=mtl-http-proxy
    FORWARDING_RULE=mtl-fw-rule-80
    FR2=mtl-fw-rule-443
    ```
    
1. **Create VPC**
    ```
    gcloud compute networks create $NETWORK --subnet-mode=custom
    ```
1. **Check that the VPC was created**
   ```
   gcloud compute networks list
    ```



### Create Network Services including the Load Balancer, the NEG, proxies and forwarding rules

1. **Create target HTTP proxy**
   ```   
    gcloud compute target-http-proxies create $TARGET_PROXY \
    --region=$REGION \
    --url-map=$URLMAP
   ```
1. **Check the proxy details**
    ```
    gcloud compute target-http-proxies list
    ```

1. **Create forwarding rule for HTTP (port 80)**
    ```   
    gcloud compute forwarding-rules create $FORWARDING_RULE \
        --region=$REGION \
        --load-balancing-scheme=EXTERNAL_MANAGED \
        --address=mtl-ip \
        --target-http-proxy=$TARGET_PROXY \
        --ports=80
    ```
    
# Forwarding rule (443)
```gcloud compute forwarding-rules create $FWR \
  --address=mtl-ip \
  --target-https-proxy=$PROXY \
  --ports=443 \
  --region=$REGION```



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
