> Why does `/ready` exist separate from `/health`?

`/health` answers the following questions:
- "Is the process alive?"
- "Is the application even working?"
All it cares about is whether or not our app is working. In the case that it fails we can be sure that our App is dead

`/ready` answers the following question:
- "is the process ready to serve traffic?"


> What should a load balance do differently when each fails?

- if `/health` fails the load balancer removes that instance and routes to other ones. 
- if `/ready` fails the load balancer keeps it in rotation but returns 503 to all users. The process is still alive but its services are unavailable 
    -  When the dependencies recover `/ready` returns 200 again and traffic resumes automatically. 
