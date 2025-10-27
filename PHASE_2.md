# SECURE ACCESS TO THE SERVICE

### Create the VPC Network with Subnet
1. Go to VPC (use the GCP search bar at the top of the console)
2. Select **+ Create a VPC network**
3. Name it **mtl-lb-network**
4. Choose your region (ours is us-west1)
5. **Custom**
1. DO NOT CREATE A SUBNET YET
2. DO NOT SELECT a FIREWALL RULE YET
3. **Disabled**
7. **Regional**
8. **Legacy**
9. DO NOT USE DNS CONFIG
10. When VPC is created, reenter and choose the SUBNETS TAB:
    1. Choose **+ Add subnet**
    1. **mtl-lb-network-subnet**
    1. Choose your region.
    1. Choose **Regional Managed Proxy**
    1. Choose **Active**
    1. Leave box unchecked I guess?
    1. Paste **10.129.0.0/23** into **IPv4 Range**
    1. Click **Add**
    1. Your subnet should appear under **Reserved proxy-only subnets for load balancing**


## Create the Load Balancer
1. Go to Network Services (use the search bar in GCP console)
1. Choose **+ Create load balancer**
2. **Application Load Balancer**
3. **Public Facing**
4. Single Region - **Best for Regional Workloads** (cheaper)
5. **Configure**
6. **mtl-load-balancer**
7. Choose region
8. Network - choose the VPC network you just created
9. Frontend configuration (side bar)
   1. **mtl-frontend**
   2. **HTTP**
   3. **Standard**
   4. Create IP Address - **mtl-frontend-ip**
   5. **Done**
1. Backend Configuration (side bar)
   1. **mtl-backend**
   2. Backend Type: **Serverless Network Endpoint Group** - Cloud Run
   3. In New Backend - choose **Create Serverless NEG**
       1. Name it **mtl-neg**
       2. Choose your CloudRun function
       3. Traffic tag - leave blank
       4. **URL Mask - we will come back to later - leave blank for now**
       5. **Create**
    1. Enable logging
    1. Cloud Armor - leave default name choice. Choose 50 requests per minute
    1. Enforce on Key -**X-Forwarded-For IP address**
1. Routing Rules - leave as default
1. Review and Finalize - just look over your entries.
1. Click **create**.    
- It takes a minute or two to create.
1. Test the load balancer by finding the IP (Port 80 just means HTTP)
2. Type http://<load balancer ip> (no 80) into a browser window.
3. You should see "Hello from Kristl's Cloud Run serverless function!..."
4. It will say Not Secure - that's okay -- that's what HTTP/Port 80 are for. 
5. Try out the diag route.
6. Try out the /auth/linkedin/start path -- it should work all the way through.
- you now have a load balancer that is not doing anything really exept forwarding your learner through to the cloud run.
- Don't worry. next step is to make it more secure. Go to the Phase 3 instructions for this. 






   

